package org.commanderlab.xmage;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;

public final class Main {

    private Main() {
    }

    public static void main(String[] args) throws Exception {
        System.setProperty("java.awt.headless", "true");

        /*
         * Fail before accepting requests if the real XMage dependency
         * cannot actually be loaded.
         */
        XmageProvider.verifyRuntimeLoaded();

        if (args.length == 3 && "phase6".equals(args[0])) {
            Phase6DifferentialAdapter.run(Path.of(args[1]), Path.of(args[2]));
            return;
        }
        if (args.length == 2) {
            // Backward-compatible B4-F file-mode form introduced before the explicit subcommand.
            Phase6DifferentialAdapter.run(Path.of(args[0]), Path.of(args[1]));
            return;
        }
        // Preserve the pre-B4-F JSONL behavior for any other argument shape: historical
        // callers may have supplied ignored launcher arguments. New file-mode callers
        // should use: phase6 <input> <output>.
        JsonlBridge bridge = new JsonlBridge();

        try (
                BufferedReader input = new BufferedReader(
                        new InputStreamReader(
                                System.in,
                                StandardCharsets.UTF_8
                        )
                );
                PrintWriter output = new PrintWriter(
                        System.out,
                        true,
                        StandardCharsets.UTF_8
                )
        ) {
            String line;

            while ((line = input.readLine()) != null) {
                if (line.isBlank()) {
                    continue;
                }

                JsonlBridge.Result result = bridge.handle(line);

                output.println(result.json());
                output.flush();

                if (result.shutdown()) {
                    break;
                }
            }
        }
    }
}
