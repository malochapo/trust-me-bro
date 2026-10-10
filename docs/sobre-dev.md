# sobre's development arms

sobre's maintainer wrote this benchmark, and pilot 1 found sobre 0.1.0-rc.1 13% dearer than Claude Code alone, and dearer than rtk. This page records what caused that, what changed in sobre, and what the change measured. The arms are `sobre-dev` and `sobre-hooks`. They sit outside the comparison of released tools: the `sobre` arm keeps its rc.1 results, and the released-tool tables never use a development build.

## What cost sobre 13% in pilot 1

The data is pilot 1's 20 sobre runs, paired with native by task and repetition.

| Runs | Cost vs native |
| --- | --- |
| All 20 sobre runs | 1.13 |
| 4 runs where sobre's post-run hook compressed a Bash output | 1.460 |
| 16 runs where it did not | 1.042 |

There were two causes.

1. **Compressing file content made the agent re-read it.** The hook compressed outputs that were source code: `sed -n 120,180p file.py`, `grep -A 20`, `git show rev:path`. The agent then read the same lines again by another command. Every run where the hook fired went this way.
2. **A fixed prefix on every request.** sobre added 922 tokens to the first request: MCP server instructions (about 600), the skill's description (110 to 160) and the deferred tool names (about 150). rtk adds 344. This prefix is written to the cache once and re-read on every later call. It cost 4.9% of a native run on average, and more on the shortest tasks.

The model made no call to a sobre MCP tool, nor to ToolSearch or the skill, in any of the 20 runs. No hook added context on any turn.

## What changed in sobre

The change is [malochapo/sobre-ai#97](https://github.com/malochapo/sobre-ai/pull/97), built in debug mode as `sobre-dev` (sha256 in `arms/versions.json`).

- **The hook compresses a command's output only when sobre has a compressor for that command,** such as git, test runners or builds. It never compresses output that one of the line's commands read from a file, and never compresses a line that runs several producing commands.
- **The prefix is shorter:** the MCP guide is 245 characters, the skill description 140, and four tool descriptions are shorter. The first request grows by 396 tokens instead of 922.

## Results

### Pilot 1: 10 tasks × 2 repetitions, all runs successful

| Arm | Mean cost per run | Cost vs native | 95% CI | Prefix tokens added | Compressed outputs |
| --- | --- | --- | --- | --- | --- |
| native | $0.0552 | 1 | | 0 | |
| sobre 0.1.0-rc.1 | $0.0623 | 1.127 | 1.040–1.239 | 922 | 4 runs |
| `sobre-dev` | $0.0557 | 1.020 | 0.974–1.072 | 396 | 0 runs |
| `sobre-hooks` | $0.0575 | 1.026 | 0.980–1.078 | 0 | 0 runs |
| rtk 0.51.0 | $0.0587 | 1.058 | 1.006–1.113 | 344 | |

Costs use the corrected price of Sonnet 5.5 cache hits ($0.10 per million tokens; PROTOCOL.md changelog). `sobre-dev` costs what native costs. `sobre-hooks` is the same build with its MCP server and skill removed. Its prompt is the size of native's (16,525 tokens on the first request, the same median), and its hook compressed nothing. On these tasks it is therefore native under another name, which makes it an A/A test. Its 1.026, with an interval that spans 1, shows how far two identical setups can drift on 10 tasks × 2 repetitions. Differences of a few percent, like the 2% the remaining prefix should cost, are below what this design can resolve.

### Pilot 2: 6 harder tasks × 2 repetitions, all runs successful

| Arm | Mean cost per run | Cost vs native | 95% CI |
| --- | --- | --- | --- |
| native | $0.077 | 1 | |
| sobre 0.1.0-rc.1 | $0.088 | 1.076 | 0.960–1.229 |
| `sobre-dev` | $0.079 | 1.011 | 0.920–1.102 |
| `sobre-hooks` | $0.074 | 0.974 | 0.827–1.088 |
| rtk 0.51.0 | $0.085 | 1.104 | 0.914–1.440 |

Pilot 2 tells the same story with wider intervals: `sobre-dev` is at parity, and `sobre-hooks` (native under another name) lands 3% under native.

### Why compressing more would gain little here

The agent already keeps its outputs small. Sonnet 5.5 pipes long outputs into `head`, `tail` or `cut`, counts matches with `grep -c`, and reads files by line range. In native runs, tool results make up about 21% of the cost in pilot 1 and 24% in pilot 2. The rest is the model's own output and the system prompt re-read on every call. More than half of those results are source code, which must reach the model as it is. Logs, git history and test output make up 5% to 12% of the cost. Folding runs of repeated log lines would have saved 0% of native's cost in pilot 1 and 1.4% in pilot 2.

So on tasks like these, a tool that only compresses output can at best match Claude Code alone. Any prompt it adds costs more than it saves.
