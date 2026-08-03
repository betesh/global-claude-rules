Never use multiple tool calls (whether in bash, python or using any other tool) to iteratively edit a single file.
If multiple lines need changes, map out all modifications upfront.
Consolidate them into a single file-write operation or a single multi-hunk edit tool call.
