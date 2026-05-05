#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <mmdeviceapi.h>
#include <audioclient.h>
#include <avrt.h>
#include <functiondiscoverykeys_devpkey.h>
#include <stdint.h>
#include <atomic>
#include <mutex>
#include <thread>
#include <vector>

#pragma comment(lib, "Ole32.lib")
#pragma comment(lib, "Avrt.lib")

// -----------------------------------------------------------------------------
// Minimal loopback capture DLL for Python ctypes.
// Exports:
//   int SetAudioCallback(AudioCallback cb)
//   int StartCaptureAsync(void** handle)
//   int StopCapture()
//
// Python side expected callback type:
//   CFUNCTYPE(None, POINTER(c_char), c_size_t)
//
// Audio format produced by this DLL:
//   PCM 16-bit, stereo, 44100 Hz
// -----------------------------------------------------------------------------

using AudioCallback = void(__cdecl*)(const char* data, size_t size);

namespace {

    struct CaptureState {
        std::atomic<bool> running{ false };
        std::atomic<bool> stopRequested{ false };
        std::thread worker;
        AudioCallback cb = nullptr;
    };

    std::mutex g_mutex;
    CaptureState* g_state = nullptr;
    AudioCallback g_callback = nullptr;

    inline HRESULT HrFromWin32(DWORD e) {
        return HRESULT_FROM_WIN32(e);
    }

    class ComInit {
    public:
        ComInit() : _hr(CoInitializeEx(nullptr, COINIT_MULTITHREADED)) {}
        ~ComInit() {
            if (SUCCEEDED(_hr)) {
                CoUninitialize();
            }
        }
        HRESULT hr() const { return _hr; }
    private:
        HRESULT _hr;
    };

    template <typename T>
    void SafeRelease(T*& p) {
        if (p) {
            p->Release();
            p = nullptr;
        }
    }

    bool IsFloatFormat(const WAVEFORMATEX* wfex) {
        if (!wfex) return false;
        if (wfex->wFormatTag == WAVE_FORMAT_IEEE_FLOAT) return true;
        if (wfex->wFormatTag == WAVE_FORMAT_EXTENSIBLE) {
            if (wfex->cbSize < 22) return false;
            auto* ext = reinterpret_cast<const WAVEFORMATEXTENSIBLE*>(wfex);
            return IsEqualGUID(ext->SubFormat, KSDATAFORMAT_SUBTYPE_IEEE_FLOAT);
        }
        return false;
    }

    bool Is16BitPCM(const WAVEFORMATEX* wfex) {
        if (!wfex) return false;
        if (wfex->wFormatTag == WAVE_FORMAT_PCM) {
            return wfex->wBitsPerSample == 16;
        }
        if (wfex->wFormatTag == WAVE_FORMAT_EXTENSIBLE) {
            if (wfex->cbSize < 22) return false;
            auto* ext = reinterpret_cast<const WAVEFORMATEXTENSIBLE*>(wfex);
            return IsEqualGUID(ext->SubFormat, KSDATAFORMAT_SUBTYPE_PCM) && ext->Format.wBitsPerSample == 16;
        }
        return false;
    }

    int16_t Clamp16(int v) {
        if (v > 32767) return 32767;
        if (v < -32768) return -32768;
        return static_cast<int16_t>(v);
    }

    void ConvertToS16Stereo44100(
        const BYTE* src,
        UINT32 frames,
        const WAVEFORMATEX* inFmt,
        DWORD flags,
        std::vector<char>& outBuf
    ) {
        constexpr int OUT_RATE = 44100;
        constexpr int OUT_CH = 2;
        constexpr int OUT_BPS = 16;
        (void)OUT_BPS;

        if (flags & AUDCLNT_BUFFERFLAGS_SILENT) {
            outBuf.assign(frames * OUT_CH * sizeof(int16_t), 0);
            return;
        }

        const int inCh = (inFmt->nChannels > 0) ? static_cast<int>(inFmt->nChannels) : 2;
        const int inRate = (inFmt->nSamplesPerSec > 0) ? static_cast<int>(inFmt->nSamplesPerSec) : 44100;

        // Fast paths only. The Python side in your test code assumes 44100/16/stereo.
        // If the endpoint mix format differs, this DLL performs simple conversion.
        if (inRate == 44100 && inCh == 2 && Is16BitPCM(inFmt)) {
            const size_t bytes = static_cast<size_t>(frames) * 2 * sizeof(int16_t);
            outBuf.assign(reinterpret_cast<const char*>(src), reinterpret_cast<const char*>(src) + bytes);
            return;
        }

        if (inRate == 44100 && IsFloatFormat(inFmt)) {
            outBuf.resize(static_cast<size_t>(frames) * 2 * sizeof(int16_t));
            auto* out = reinterpret_cast<int16_t*>(outBuf.data());
            const float* in = reinterpret_cast<const float*>(src);

            for (UINT32 i = 0; i < frames; ++i) {
                float l = 0.0f;
                float r = 0.0f;
                if (inCh == 1) {
                    l = r = in[i];
                }
                else {
                    l = in[i * inCh + 0];
                    r = in[i * inCh + 1];
                }
                int li = static_cast<int>(l * 32767.0f);
                int ri = static_cast<int>(r * 32767.0f);
                out[i * 2 + 0] = Clamp16(li);
                out[i * 2 + 1] = Clamp16(ri);
            }
            return;
        }

        if (inRate == 44100 && inCh == 1 && Is16BitPCM(inFmt)) {
            outBuf.resize(static_cast<size_t>(frames) * 2 * sizeof(int16_t));
            auto* out = reinterpret_cast<int16_t*>(outBuf.data());
            const int16_t* in = reinterpret_cast<const int16_t*>(src);
            for (UINT32 i = 0; i < frames; ++i) {
                out[i * 2 + 0] = in[i];
                out[i * 2 + 1] = in[i];
            }
            return;
        }

        // Slow fallback: nearest-neighbor resample + channel conversion.
        const UINT32 outFrames = static_cast<UINT32>((static_cast<uint64_t>(frames) * 44100ull) / static_cast<uint64_t>(inRate));
        outBuf.resize(static_cast<size_t>(outFrames) * 2 * sizeof(int16_t));
        auto* out = reinterpret_cast<int16_t*>(outBuf.data());

        for (UINT32 of = 0; of < outFrames; ++of) {
            const UINT32 inf = static_cast<UINT32>((static_cast<uint64_t>(of) * static_cast<uint64_t>(inRate)) / 44100ull);

            float l = 0.0f;
            float r = 0.0f;

            if (IsFloatFormat(inFmt)) {
                const float* in = reinterpret_cast<const float*>(src);
                if (inCh == 1) {
                    l = r = in[inf];
                }
                else {
                    l = in[inf * inCh + 0];
                    r = in[inf * inCh + 1];
                }
            }
            else if (Is16BitPCM(inFmt)) {
                const int16_t* in = reinterpret_cast<const int16_t*>(src);
                if (inCh == 1) {
                    const float s = static_cast<float>(in[inf]) / 32768.0f;
                    l = r = s;
                }
                else {
                    l = static_cast<float>(in[inf * inCh + 0]) / 32768.0f;
                    r = static_cast<float>(in[inf * inCh + 1]) / 32768.0f;
                }
            }
            else {
                l = r = 0.0f;
            }

            out[of * 2 + 0] = Clamp16(static_cast<int>(l * 32767.0f));
            out[of * 2 + 1] = Clamp16(static_cast<int>(r * 32767.0f));
        }
    }

    DWORD CaptureThreadMain(CaptureState* state) {
        HRESULT hr = S_OK;
        ComInit com;
        if (FAILED(com.hr())) return static_cast<DWORD>(com.hr());

        IMMDeviceEnumerator* enumerator = nullptr;
        IMMDevice* device = nullptr;
        IAudioClient* audioClient = nullptr;
        IAudioCaptureClient* captureClient = nullptr;
        WAVEFORMATEX* mixFormat = nullptr;
        HANDLE hEvent = nullptr;
        HANDLE hTask = nullptr;
        DWORD taskIndex = 0;
        REFERENCE_TIME bufferDuration = 0;

        hr = CoCreateInstance(__uuidof(MMDeviceEnumerator), nullptr, CLSCTX_ALL,
            __uuidof(IMMDeviceEnumerator), reinterpret_cast<void**>(&enumerator));
        if (FAILED(hr)) goto cleanup;

        hr = enumerator->GetDefaultAudioEndpoint(eRender, eConsole, &device);
        if (FAILED(hr)) goto cleanup;

        hr = device->Activate(__uuidof(IAudioClient), CLSCTX_ALL, nullptr, reinterpret_cast<void**>(&audioClient));
        if (FAILED(hr)) goto cleanup;

        hr = audioClient->GetMixFormat(&mixFormat);
        if (FAILED(hr)) goto cleanup;

        hEvent = CreateEventW(nullptr, FALSE, FALSE, nullptr);
        if (!hEvent) {
            hr = HrFromWin32(GetLastError());
            goto cleanup;
        }

        // Event-driven shared loopback.
        hr = audioClient->Initialize(
            AUDCLNT_SHAREMODE_SHARED,
            AUDCLNT_STREAMFLAGS_LOOPBACK | AUDCLNT_STREAMFLAGS_EVENTCALLBACK,
            bufferDuration,
            0,
            mixFormat,
            nullptr
        );
        if (FAILED(hr)) goto cleanup;

        hr = audioClient->SetEventHandle(hEvent);
        if (FAILED(hr)) goto cleanup;

        hr = audioClient->GetService(__uuidof(IAudioCaptureClient), reinterpret_cast<void**>(&captureClient));
        if (FAILED(hr)) goto cleanup;

        hTask = AvSetMmThreadCharacteristicsW(L"Audio", &taskIndex);

        hr = audioClient->Start();
        if (FAILED(hr)) goto cleanup;

        state->running = true;

        while (!state->stopRequested.load()) {
            DWORD waitResult = WaitForSingleObject(hEvent, 200);
            if (waitResult != WAIT_OBJECT_0) {
                continue;
            }

            while (true) {
                UINT32 packetFrames = 0;
                hr = captureClient->GetNextPacketSize(&packetFrames);
                if (FAILED(hr)) goto cleanup;
                if (packetFrames == 0) break;

                BYTE* data = nullptr;
                UINT32 frames = 0;
                DWORD flags = 0;
                hr = captureClient->GetBuffer(&data, &frames, &flags, nullptr, nullptr);
                if (FAILED(hr)) goto cleanup;

                AudioCallback cb = nullptr;
                {
                    std::lock_guard<std::mutex> lock(g_mutex);
                    cb = state->cb;
                }

                if (cb && frames > 0) {
                    std::vector<char> converted;
                    ConvertToS16Stereo44100(data, frames, mixFormat, flags, converted);
                    if (!converted.empty()) {
                        cb(converted.data(), converted.size());
                    }
                }

                hr = captureClient->ReleaseBuffer(frames);
                if (FAILED(hr)) goto cleanup;
            }
        }

        audioClient->Stop();
        hr = S_OK;

    cleanup:
        if (hTask) {
            AvRevertMmThreadCharacteristics(hTask);
            hTask = nullptr;
        }
        if (hEvent) {
            CloseHandle(hEvent);
            hEvent = nullptr;
        }
        if (mixFormat) {
            CoTaskMemFree(mixFormat);
            mixFormat = nullptr;
        }
        SafeRelease(captureClient);
        SafeRelease(audioClient);
        SafeRelease(device);
        SafeRelease(enumerator);

        state->running = false;
        return static_cast<DWORD>(hr);
    }

} // namespace

extern "C" __declspec(dllexport) int __cdecl SetAudioCallback(AudioCallback cb) {
    std::lock_guard<std::mutex> lock(g_mutex);
    g_callback = cb;
    if (g_state) {
        g_state->cb = cb;
    }
    return 0;
}

extern "C" __declspec(dllexport) int __cdecl StartCaptureAsync(void** ppCapture) {
    if (!ppCapture) return static_cast<int>(E_POINTER);

    std::lock_guard<std::mutex> lock(g_mutex);
    if (g_state) {
        return static_cast<int>(E_UNEXPECTED);
    }

    CaptureState* state = new (std::nothrow) CaptureState();
    if (!state) return static_cast<int>(E_OUTOFMEMORY);
    state->cb = g_callback;

    try {
        state->worker = std::thread([state]() {
            CaptureThreadMain(state);
            });
    }
    catch (...) {
        delete state;
        return static_cast<int>(E_FAIL);
    }

    // Wait briefly until the worker transitions into running or exits early.
    for (int i = 0; i < 200; ++i) {
        if (state->running.load()) break;
        if (!state->worker.joinable()) break;
        Sleep(10);
    }

    *ppCapture = state;
    g_state = state;
    return 0;
}

extern "C" __declspec(dllexport) int __cdecl StopCapture() {
    CaptureState* state = nullptr;
    {
        std::lock_guard<std::mutex> lock(g_mutex);
        state = g_state;
        g_state = nullptr;
    }

    if (!state) return 0;

    state->stopRequested = true;
    if (state->worker.joinable()) {
        state->worker.join();
    }
    delete state;
    return 0;
}

BOOL APIENTRY DllMain(HMODULE, DWORD, LPVOID) {
    return TRUE;
}
