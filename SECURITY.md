# Security

The benchmark runs coding agents with API keys. The harness reads each key from the environment (`BENCH_KEY_<ARM>`, `BENCH_KEY_JUDGE`) and never writes it to disk. Run transcripts are published, so they are checked for keys and other secrets before each publication.

If you find a key, a token or other sensitive data in this repository or its history, do not open a public issue. Report it privately instead: on GitHub, go to the repository's **Security** tab and choose **Report a vulnerability**. The key will be revoked and the data removed from the repository.
