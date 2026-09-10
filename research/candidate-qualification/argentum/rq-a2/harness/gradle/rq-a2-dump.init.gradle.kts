// RQ-A2 external init script: dumps resolvable runtime classpaths to build/
// files WITHOUT modifying the candidate build. Lives CPL-side; applied via -I.
import org.gradle.api.plugins.JavaPluginExtension
import org.gradle.jvm.tasks.Jar

allprojects {
    tasks.register("rqA2DumpClasspath") {
        doLast {
            if (project.name in setOf("rules-engine", "mtg-sdk", "gym", "game-server")) {
                val runtime = project.configurations.findByName("runtimeClasspath")
                    ?.incoming?.artifacts?.artifactFiles?.files
                    ?.joinToString("\n") { it.absolutePath } ?: ""
                val mainOut = project.extensions.findByType(JavaPluginExtension::class.java)
                    ?.sourceSets?.getByName("main")?.output?.classesDirs?.files
                    ?.joinToString("\n") { it.absolutePath } ?: ""
                val jarTask = project.tasks.findByName("jar") as? Jar
                val jarPath = jarTask?.archiveFile?.get()?.asFile?.absolutePath ?: ""
                project.layout.buildDirectory.file("rq-a2-classpath.txt").get().asFile
                    .apply { parentFile.mkdirs() }
                    .writeText(listOf(jarPath, mainOut, runtime).filter { it.isNotEmpty() }.joinToString("\n"))
                println("RQ-A2-DUMP ${project.name} -> ${project.layout.buildDirectory.file("rq-a2-classpath.txt").get().asFile}")
            }
        }
    }
}
