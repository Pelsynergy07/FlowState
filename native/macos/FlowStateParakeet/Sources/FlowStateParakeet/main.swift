// A long-running speech worker. FlowState (Python) starts it once, waits
// for {"ready":true}, then writes one JSON request per line:
//   {"id": 1, "path": "/path/to/16k.wav"}
// and reads one JSON reply per line:
//   {"id": 1, "text": "...", "duration": 3.2, "seconds": 0.08,
//    "tokens": [["▁Hello", 0.0, 0.32], ...]}
// or {"id": 1, "error": "..."}. Closing stdin ends the process.
//
// Models load once, so each live window transcribes in about 0.1 s.

import CoreML
import FluidAudio
import Foundation

func emit(_ object: [String: Any]) {
    guard let data = try? JSONSerialization.data(withJSONObject: object),
          let line = String(data: data, encoding: .utf8) else { return }
    print(line)
    fflush(stdout)
}

@MainActor
func run() async {
    let args = CommandLine.arguments
    guard args.count >= 2 else {
        emit(["error": "usage: FlowStateParakeet <model folder>"])
        exit(2)
    }
    let folder = URL(fileURLWithPath: args[1], isDirectory: true)
    let version: AsrModelVersion = .v2
    do {
        ModelHub.offlineMode = true  // FlowState downloads the model itself
        let started = ProcessInfo.processInfo.systemUptime
        let cpu = MLModelConfiguration()
        cpu.computeUnits = .cpuOnly
        let neural = MLModelConfiguration()
        neural.computeUnits = .cpuAndNeuralEngine
        let vocabData = try Data(contentsOf: folder.appendingPathComponent("parakeet_vocab.json"))
        let vocabulary = try JSONDecoder().decode([Int: String].self, from: vocabData)
        func model(_ name: String, _ config: MLModelConfiguration) throws -> MLModel {
            try MLModel(contentsOf: folder.appendingPathComponent(name), configuration: config)
        }
        let models = AsrModels(
            encoder: try model("Encoder.mlmodelc", neural),
            preprocessor: try model("Preprocessor.mlmodelc", cpu),
            decoder: try model("Decoder.mlmodelc", neural),
            joint: try model("JointDecision.mlmodelc", neural),
            configuration: neural,
            vocabulary: vocabulary,
            version: version
        )
        let manager = AsrManager(config: .default)
        try await manager.loadModels(models)
        emit(["ready": true, "load_seconds": ProcessInfo.processInfo.systemUptime - started])

        while let line = readLine() {
            guard let data = line.data(using: .utf8),
                  let request = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let path = request["path"] as? String else { continue }
            let id = request["id"] ?? NSNull()
            do {
                var state = try TdtDecoderState(decoderLayers: version.decoderLayers)
                let began = ProcessInfo.processInfo.systemUptime
                let result = try await manager.transcribe(URL(fileURLWithPath: path), decoderState: &state)
                let tokens: [[Any]] = (result.tokenTimings ?? []).map {
                    [$0.token, $0.startTime, $0.endTime]
                }
                emit(["id": id, "text": result.text, "duration": result.duration,
                      "seconds": ProcessInfo.processInfo.systemUptime - began, "tokens": tokens])
            } catch {
                emit(["id": id, "error": String(describing: error)])
            }
        }
    } catch {
        emit(["error": String(describing: error)])
        exit(1)
    }
}

await run()
