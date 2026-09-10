package rqa2

// Minimal JSON builder (no extra plugin needed; full control over output).
sealed interface J {
    fun render(sb: StringBuilder)
}

private fun esc(s: String): String = buildString {
    append('"')
    for (c in s) when (c) {
        '"' -> append("\\\"")
        '\\' -> append("\\\\")
        '\n' -> append("\\n")
        '\r' -> append("\\r")
        '\t' -> append("\\t")
        else -> if (c < ' ') append("\\u%04x".format(c.code)) else append(c)
    }
    append('"')
}

data class JO(val map: LinkedHashMap<String, Any?> = LinkedHashMap()) : J {
    override fun render(sb: StringBuilder) {
        sb.append('{')
        var first = true
        for ((k, v) in map) {
            if (!first) sb.append(',')
            first = false
            sb.append(esc(k)).append(':')
            renderValue(sb, v)
        }
        sb.append('}')
    }
    operator fun set(k: String, v: Any?) { map[k] = v }
}

data class JA(val list: List<Any?> = emptyList()) : J {
    override fun render(sb: StringBuilder) {
        sb.append('[')
        var first = true
        for (v in list) {
            if (!first) sb.append(',')
            first = false
            renderValue(sb, v)
        }
        sb.append(']')
    }
}

fun renderValue(sb: StringBuilder, v: Any?) {
    when (v) {
        null -> sb.append("null")
        is J -> v.render(sb)
        is String -> sb.append(esc(v))
        is Number, is Boolean -> sb.append(v.toString())
        is List<*> -> JA(v).render(sb)
        is Map<*, *> -> {
            val jo = JO()
            for ((k, vv) in v) jo[k.toString()] = vv
            jo.render(sb)
        }
        else -> sb.append(esc(v.toString()))
    }
}

fun jo(vararg pairs: Pair<String, Any?>): JO = JO(LinkedHashMap<String, Any?>().also {
    for ((k, v) in pairs) it[k] = v
})

fun ja(vararg items: Any?): JA = JA(items.toList())

fun J.toJsonString(): String = buildString { render(this) }

fun writeJson(path: String, root: J) {
    val f = java.io.File(path)
    f.parentFile?.mkdirs()
    f.writeText(root.toJsonString())
}
