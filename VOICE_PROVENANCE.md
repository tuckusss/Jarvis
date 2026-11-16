# Offline JARVIS neural voice asset provenance

The setup bundle includes the following third-party voice components:

- Kokoro ONNX Python wrapper by thewh1teagle, MIT license:
  https://github.com/thewh1teagle/kokoro-onnx
- Kokoro-82M speech model / en-GB voice embeddings, Apache 2.0:
  https://huggingface.co/hexgrad/Kokoro-82M
- Redistributable, quantized ONNX model files (GitHub release):
  https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.1

The installer build downloads exact assets below and rejects SHA256 mismatches:

- kokoro-v1.0.int8.onnx:
  ae315a79b623f244700e4afb9246c46a26066782e049ba174bf3ba433970ee9c
- voices-v1.0.bin:
  bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d

Full Apache 2.0 and MIT licence texts are downloaded into the installed application's
licenses directory during the build. These permissions do not automatically apply
to the JARVIS source code itself. Third-party software dependencies have their own
licenses and may require attribution before public distribution.

The neural ONNX model-files-v1.1 release uses floating-point speed inputs; JARVIS pins `kokoro-onnx==0.6.1` to use the newer wrapper's correct model input type detection. Old wrapper 0.5.0 failed CI synthesis due to tensor(int32) versus tensor(float).
