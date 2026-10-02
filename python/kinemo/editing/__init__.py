"""Editing scene source from tools (the `kinemo dev` preview).

The code stays the only source of truth: tools read the arguments of the calls that built
the scene (located by the exact spans the runtime records) and change them by rewriting
just those characters in the file. Nothing here keeps state the code does not have.

- `call_sites`: find the call behind a span and describe its arguments.
- `literals`: which argument values are plain literals a tool may rewrite.
- `source_edit`: apply a set of argument changes to a file's text, refusing stale edits.
- `scene_index`: the call sites of a built scene, as JSON for the preview.
- `overrides`: load a scene from edited text without writing it (live previews).
"""
