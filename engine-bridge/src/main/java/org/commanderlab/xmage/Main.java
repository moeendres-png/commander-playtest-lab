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

        if (args.length == 2) {
            Phase6DifferentialAdapter.run(Path.of(args[0]), Path.of(args[1]));
            return;
        }
        if (args.length != 0) {
            throw new IllegalArgumentException(
                    "expected zero args for JSONL bridge mode or <input> <output> for Phase-6 differential mode"
            );
        }

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
