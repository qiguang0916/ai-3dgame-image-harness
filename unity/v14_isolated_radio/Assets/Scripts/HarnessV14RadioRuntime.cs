using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using UnityEngine;
using UnityEngine.SceneManagement;

public sealed class HarnessV14RadioRuntime : MonoBehaviour
{
    // This is a visual asset-import QA fixture, not a 3D game or a rights review.
    public string ExpectedSourceSha256 = "";
    public string ImportedTextureAssetPath = "Assets/PrivateRadio/RadioAccepted.png";
    public int ExpectedTextureWidth = 1536;
    public int ExpectedTextureHeight = 1024;

    [Serializable]
    private sealed class FrameEvidence
    {
        public string status;
        public string captureKind;
        public string unityVersion;
        public string sourceSha256;
        public string screenshotSha256;
        public string screenshotPath;
        public string scene;
        public string graphicsDeviceName;
        public string graphicsDeviceType;
        public string runtimePlatform;
        public string capturedUtc;
        public bool developmentBuild;
        public int screenWidth;
        public int screenHeight;
        public int frameSamples;
        public float medianFrameMilliseconds;
        public float p95FrameMilliseconds;
        public long managedMemoryBytes;
        public string limitations;
    }

    private static string Arg(string key)
    {
        string[] argv = Environment.GetCommandLineArgs();
        for (int i = 0; i + 1 < argv.Length; i++)
            if (string.Equals(argv[i], key, StringComparison.Ordinal))
                return argv[i + 1];
        return null;
    }

    private static string Sha(string filename)
    {
        using (var hash = SHA256.Create())
        using (var stream = File.OpenRead(filename))
        {
            byte[] digest = hash.ComputeHash(stream);
            var builder = new StringBuilder(digest.Length * 2);
            foreach (byte b in digest) builder.Append(b.ToString("x2"));
            return builder.ToString();
        }
    }

    private static float Percentile(List<float> xs, double fraction)
    {
        if (xs.Count == 0) return -1;
        xs.Sort();
        return xs[Mathf.Clamp(Mathf.RoundToInt((float)((xs.Count - 1) * fraction)), 0, xs.Count - 1)];
    }

    private IEnumerator Start()
    {
        string dest = Arg("-harnessV14EvidenceDir");
        if (string.IsNullOrEmpty(dest))
        {
            UnityEngine.Debug.LogError("HARNESS_V14_CAPTURE_NOT_REQUESTED");
            yield break;
        }

        if (Directory.Exists(dest))
        {
            UnityEngine.Debug.LogError("HARNESS_V14_REFUSE_EXISTING_DESTINATION");
            Application.Quit(2);
            yield break;
        }

        Directory.CreateDirectory(dest);
        string capture = Path.Combine(dest, "radio-player.png");
        string report = Path.Combine(dest, "player-report.json");
        QualitySettings.vSyncCount = 0;
        Application.targetFrameRate = 60;

        // Explicitly capture from the actual running Player's rendered frame.
        for (int k = 0; k < 12; k++) yield return new WaitForEndOfFrame();
        var timings = new List<float>();
        for (int k = 0; k < 100; k++)
        {
            yield return new WaitForEndOfFrame();
            if (Time.unscaledDeltaTime > 0.001f && Time.unscaledDeltaTime < 1f)
                timings.Add(Time.unscaledDeltaTime * 1000f);
        }

        ScreenCapture.CaptureScreenshot(capture, 1);
        UnityEngine.Debug.Log("HARNESS_V14_CAPTURE_REQUESTED " + capture);
        long last = 0;
        int stable = 0;
        bool ready = false;
        for (int k = 0; k < 300; k++)
        {
            yield return null;
            if (File.Exists(capture))
            {
                long len = new FileInfo(capture).Length;
                if (len > 1024 && len == last) stable++;
                else stable = 0;
                last = len;
                if (stable >= 5) { ready = true; break; }
            }
        }

        string shotSha = ready ? Sha(capture) : "";
        var record = new FrameEvidence {
            status = ready ? "PLAYER_FRAME_CAPTURED_NOT_COMMERCIAL_APPROVED" : "BLOCKED_NO_CAPTURE",
            captureKind = "REAL_IN_ENGINE_UNITY_SCREEN_CAPTURE",
            unityVersion = Application.unityVersion,
            sourceSha256 = ExpectedSourceSha256,
            screenshotSha256 = shotSha,
            screenshotPath = capture,
            scene = SceneManager.GetActiveScene().name,
            graphicsDeviceName = SystemInfo.graphicsDeviceName,
            graphicsDeviceType = SystemInfo.graphicsDeviceType.ToString(),
            runtimePlatform = Application.platform.ToString(),
            developmentBuild = UnityEngine.Debug.isDebugBuild,
            capturedUtc = DateTime.UtcNow.ToString("O"),
            screenWidth = Screen.width,
            screenHeight = Screen.height,
            frameSamples = timings.Count,
            medianFrameMilliseconds = Percentile(timings, .5),
            p95FrameMilliseconds = Percentile(timings, .95),
            managedMemoryBytes = GC.GetTotalMemory(false),
            limitations = "Only standalone textured-quad image asset acceptance. No actual in-game 3D model, physics, input, frame-time guarantee, human material approval, rights, Steam approval."
        };

        File.WriteAllText(report, JsonUtility.ToJson(record, true) + "\n");
        UnityEngine.Debug.Log("HARNESS_V14_PLAYER_EVIDENCE "
            + record.status + " " + record.screenshotSha256
            + " frames=" + record.frameSamples
            + " source=" + record.sourceSha256);
        Application.Quit(ready ? 0 : 2);
    }
}

