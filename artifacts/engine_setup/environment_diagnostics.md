# Engine setup environment diagnostics

Generated: `2026-08-04T18:59:46.799215Z`

## Platform

- OS: `Linux 6.12.13`
- Architecture: `x86_64`
- CPU cores visible: `5`
- Free storage: `38.8 GiB`
- Repository writable: `True`

## Toolchain

| Tool | Status | Version/output |
|---|---|---|
| java | available | `openjdk version "21.0.10" 2026-01-20<br>OpenJDK Runtime Environment (build 21.0.10+7-Debian-1deb13u1)<br>OpenJDK 64-Bit Server VM (build 21.0.10+7-Debian-1deb13u1, mixed mode, sharing)` |
| javac | available | `javac 21.0.10` |
| maven | unavailable | `[Errno 2] No such file or directory: 'mvn'` |
| gradle | unavailable | `[Errno 2] No such file or directory: 'gradle'` |
| git | available | `git version 2.47.3` |
| docker | unavailable | `[Errno 2] No such file or directory: 'docker'` |
| docker_compose | unavailable | `[Errno 2] No such file or directory: 'docker'` |
| python | available | `Python 3.13.5` |

## Network

- DNS `github.com`: `{'ok': False, 'error': "gaierror(-3, 'Temporary failure in name resolution')"}`
- DNS `raw.githubusercontent.com`: `{'ok': False, 'error': "gaierror(-3, 'Temporary failure in name resolution')"}`
- DNS `repo.maven.apache.org`: `{'ok': False, 'error': "gaierror(-3, 'Temporary failure in name resolution')"}`

## Preliminary conclusion

- Missing/unusable tools: `maven, gradle, docker, docker_compose`
- GitHub DNS: `False`
- Maven Central DNS: `False`
