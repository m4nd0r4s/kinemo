# Security policy

## Reporting a vulnerability

Please report security issues privately through GitHub: on the repository's **Security** tab,
choose **Report a vulnerability**. Do not open a public issue for them.

Include what you found, how to reproduce it and the version of kinemo. You will get an answer
within a week, and a fix or a plan within thirty days for confirmed issues.

## Scope

kinemo runs the scene files you give it: a scene is Python code, with the same rights as any
script you run. Running an untrusted scene is not a vulnerability in kinemo.

In scope, for example:

- `kinemo dev` serving files or accepting edits from outside `127.0.0.1`, or an edit from the
  preview page writing outside the files of the scene being previewed;
- the MCP server (`kinemo mcp`) acting beyond the files and scenes it was asked about;
- crashes or memory safety issues in the native core triggered by a scene's data (images,
  SVG, fonts, data frames) rather than by its code.

## Supported versions

Security fixes go into the latest release.
