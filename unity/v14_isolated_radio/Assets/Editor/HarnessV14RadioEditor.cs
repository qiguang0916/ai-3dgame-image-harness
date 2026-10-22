using System;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

public static class HarnessV14RadioEditor
{
    private const string RelativeRadio = "Assets/PrivateRadio/RadioAccepted.png";
    private const string RelativeScene = "Assets/Scenes/V14RadioTextureAcceptance.unity";

    [Serializable]
    private sealed class ImportReport
    {
        public string status;
        public string unityVersion;
        public string imageSourceSha256;
        public string imageImportedSha256;
        public string assetPath;
        public string assetGuid;
        public string graphicsDevice;
        public string editorRenderedSha256;
        public string editorRenderedStatus;
        public string buildResult;
        public string buildPlayerPath;
        public string observedUtc;
        public string limitations;
        public bool importedImageMatchesSourceBytes;
        public bool editorCaptureIsRealUnityRender;
        public bool developmentBuild;
        public int importedWidth;
        public int importedHeight;
        public int sourceByteLength;
        public long buildSizeBytes;
        public int editorNonbackgroundSamples;
        public float quadFacingCameraDot;
    }

    private static string Argument(string key)
    {
        string[] args = Environment.GetCommandLineArgs();
        for (int i = 0; i + 1 < args.Length; i++)
            if (string.Equals(args[i], key, StringComparison.Ordinal))
                return args[i + 1];
        return null;
    }

    private static string Digest(string path)
    {
        using (var h = SHA256.Create())
        using (var f = File.OpenRead(path))
        {
            var result = h.ComputeHash(f);
            var builder = new StringBuilder(result.Length * 2);
            foreach (var x in result) builder.Append(x.ToString("x2"));
            return builder.ToString();
        }
    }

    public static void Execute()
    {
        string expected = Argument("-harnessV14ExpectedSha");
        string evidence = Argument("-harnessV14OutputDir");
        string project = Path.GetFullPath(Path.Combine(Application.dataPath, ".."));
        string source = Path.Combine(project, RelativeRadio);
        if (string.IsNullOrEmpty(expected) || expected.Length != 64 || string.IsNullOrEmpty(evidence))
            throw new InvalidOperationException("HARNESS_V14_REQUIRED_EXPECTED_SHA_AND_EVIDENCE_DIR");
        if (!File.Exists(source) || !string.Equals(Digest(source), expected, StringComparison.Ordinal))
            throw new InvalidOperationException("HARNESS_V14_PRIVATE_SOURCE_SHA_MISMATCH");
        if (Directory.Exists(evidence))
            throw new InvalidOperationException("HARNESS_V14_EVIDENCE_DIR_ALREADY_EXISTS");

        Directory.CreateDirectory(evidence);
        string log = Path.Combine(evidence, "editor-report.json");
        var report = new ImportReport {
            status = "BLOCKED",
            unityVersion = Application.unityVersion,
            imageSourceSha256 = expected,
            imageImportedSha256 = Digest(source),
            assetPath = RelativeRadio,
            graphicsDevice = SystemInfo.graphicsDeviceName,
            sourceByteLength = (int)(new FileInfo(source).Length),
            observedUtc = DateTime.UtcNow.ToString("O"),
            limitations = "Standalone private textured quad inspection only, not a 3D modeled radio; build and screenshots never certify game behavior, art, rights, Steam.",
            developmentBuild = false,
        };

        try
        {
            AssetDatabase.ImportAsset(RelativeRadio, ImportAssetOptions.ForceSynchronousImport);
            var importer = AssetImporter.GetAtPath(RelativeRadio) as TextureImporter;
            if (importer == null) throw new InvalidOperationException("HARNESS_V14_NO_PNG_IMPORTER");
            importer.textureType = TextureImporterType.Default;
            importer.sRGBTexture = true;
            importer.alphaSource = TextureImporterAlphaSource.None;
            importer.mipmapEnabled = false;
            importer.textureCompression = TextureImporterCompression.Uncompressed;
            importer.maxTextureSize = 2048;
            importer.npotScale = TextureImporterNPOTScale.None;
            importer.isReadable = true;
            importer.filterMode = FilterMode.Bilinear;
            importer.SaveAndReimport();

            Texture2D original = AssetDatabase.LoadAssetAtPath<Texture2D>(RelativeRadio);
            if (original == null || original.width != 1536 || original.height != 1024)
                throw new InvalidOperationException("HARNESS_V14_RADIO_TEXTURE_DIMENSIONS_MISMATCH");

            report.importedWidth = original.width;
            report.importedHeight = original.height;
            report.assetGuid = AssetDatabase.AssetPathToGUID(RelativeRadio);
            report.importedImageMatchesSourceBytes = string.Equals(Digest(source), expected, StringComparison.Ordinal);

            Scene scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            GameObject radio = GameObject.CreatePrimitive(PrimitiveType.Quad);
            radio.name = "RADIO_001_RealImage_Standalone_Visual_QA";
            radio.transform.position = Vector3.zero;
            radio.transform.rotation = Quaternion.identity;
            radio.transform.localScale = new Vector3(6, 4, 1);
            var shader = Shader.Find("Unlit/Texture");
            if (shader == null) throw new InvalidOperationException("HARNESS_V14_UNLIT_SHADER_MISSING");
            Material material = new Material(shader);
            material.name = "V14RadioUnlit";
            material.mainTexture = original;
            string materialFile = "Assets/PrivateRadio/RadioAcceptance.mat";
            if (AssetDatabase.LoadAssetAtPath<Material>(materialFile) != null)
                throw new InvalidOperationException("HARNESS_V14_MATERIAL_ALREADY_EXISTS");
            AssetDatabase.CreateAsset(material, materialFile);
            radio.GetComponent<MeshRenderer>().sharedMaterial =
                AssetDatabase.LoadAssetAtPath<Material>(materialFile);

            GameObject cameraObject = new GameObject("RADIO_001_Visual_QA_Camera");
            var cam = cameraObject.AddComponent<Camera>();
            cam.orthographic = true;
            cam.orthographicSize = 2.55f;
            cam.nearClipPlane = .01f;
            cam.farClipPlane = 50;
            cam.clearFlags = CameraClearFlags.SolidColor;
            cam.backgroundColor = new Color(.066f, .084f, .095f, 1);
            cam.transform.position = new Vector3(0, 0, 9);
            cam.transform.rotation = Quaternion.Euler(0, 180, 0);
            cam.depth = 0;
            Vector3 geometricNormal = radio.GetComponent<MeshFilter>().sharedMesh.normals[0];
            Vector3 toCamera = (cam.transform.position - radio.transform.position).normalized;
            float facing = Vector3.Dot(radio.transform.TransformDirection(geometricNormal), toCamera);
            if (facing <= 0)
                radio.transform.rotation = Quaternion.Euler(0, 180, 0);
            facing = Vector3.Dot(radio.transform.TransformDirection(geometricNormal), toCamera);
            report.quadFacingCameraDot = facing;
            if (facing <= .9f)
                throw new InvalidOperationException("HARNESS_V14_QUAD_DOES_NOT_FACE_CAMERA");

            var witness = cameraObject.AddComponent<HarnessV14RadioRuntime>();
            witness.ExpectedSourceSha256 = expected;
            witness.ExpectedTextureWidth = original.width;
            witness.ExpectedTextureHeight = original.height;
            witness.ImportedTextureAssetPath = RelativeRadio;

            if (!Directory.Exists(Path.Combine(Application.dataPath, "Scenes")))
                Directory.CreateDirectory(Path.Combine(Application.dataPath, "Scenes"));
            if (!EditorSceneManager.SaveScene(scene, RelativeScene))
                throw new InvalidOperationException("HARNESS_V14_SCENE_SAVE_FAILED");
            EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene(RelativeScene, true) };
            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();

            // Render a real scene frame in the Unity Editor graphics device.
            // Do not label this PASS until an external verifier inspects pixels.
            RenderTexture buffer = null;
            Texture2D picture = null;
            RenderTexture previous = RenderTexture.active;
            try
            {
                buffer = new RenderTexture(1280, 800, 24, RenderTextureFormat.ARGB32);
                buffer.Create();
                cam.targetTexture = buffer;
                cam.Render();
                RenderTexture.active = buffer;
                picture = new Texture2D(1280, 800, TextureFormat.RGB24, false);
                picture.ReadPixels(new Rect(0, 0, 1280, 800), 0, 0);
                picture.Apply();
                string preview = Path.Combine(evidence, "editor-scene.png");
                File.WriteAllBytes(preview, picture.EncodeToPNG());
                report.editorRenderedSha256 = Digest(preview);
                Color32 background = (Color32)cam.backgroundColor;
                Color32[] visible = picture.GetPixels32();
                int nonBackground = 0;
                for (int y = 0; y < 800; y += 8)
                for (int x = 0; x < 1280; x += 8)
                {
                    Color32 pixel = visible[y * 1280 + x];
                    int contrast = Math.Abs(pixel.r - background.r) +
                                   Math.Abs(pixel.g - background.g) +
                                   Math.Abs(pixel.b - background.b);
                    if (contrast > 50) nonBackground++;
                }
                report.editorNonbackgroundSamples = nonBackground;
                if (nonBackground < 1500)
                    throw new InvalidOperationException("HARNESS_V14_EMPTY_EDITOR_CAPTURE");
                report.editorRenderedStatus = "UNITY_EDITOR_RENDER_CONTENT_OBSERVED_NOT_ART_APPROVED";
                report.editorCaptureIsRealUnityRender = true;
                UnityEngine.Debug.Log("HARNESS_V14_EDITOR_SCENE_CAPTURE " + preview + " " + report.editorRenderedSha256);
            }
            catch (Exception ex)
            {
                report.editorRenderedStatus = "BLOCKED_RENDER_CAPTURE: " + ex.GetType().Name;
                UnityEngine.Debug.LogWarning("HARNESS_V14_EDITOR_SCENE_CAPTURE_BLOCKED " + ex.GetType().Name);
            }
            finally
            {
                cam.targetTexture = null;
                RenderTexture.active = previous;
                if (picture != null) UnityEngine.Object.DestroyImmediate(picture);
                if (buffer != null) { buffer.Release(); UnityEngine.Object.DestroyImmediate(buffer); }
            }

            string buildPath = Path.Combine(evidence, "RadioImageAcceptance.app");
            var options = new BuildPlayerOptions {
                scenes = new[] { RelativeScene },
                locationPathName = buildPath,
                target = BuildTarget.StandaloneOSX,
                options = BuildOptions.None
            };
            BuildReport build = BuildPipeline.BuildPlayer(options);
            report.buildResult = build.summary.result.ToString();
            report.buildSizeBytes = (long)build.summary.totalSize;
            report.buildPlayerPath = buildPath;
            if (build.summary.result != BuildResult.Succeeded)
                throw new InvalidOperationException("HARNESS_V14_PLAYER_BUILD_FAILED_" + report.buildResult);
            report.status = "UNITY_EDITOR_IMPORTED_PLAYER_BUILT_NOT_ART_APPROVED";
            UnityEngine.Debug.Log("HARNESS_V14_EDITOR_IMPORT_DONE " + expected + " " + report.buildResult);
        }
        finally
        {
            File.WriteAllText(log, JsonUtility.ToJson(report, true) + "\n");
        }
    }
}

