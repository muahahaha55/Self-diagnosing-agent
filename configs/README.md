# configs

## `mistral_nemo_chat_template.jinja`

The chat template of `mistralai/Mistral-Nemo-Instruct-2407`, copied verbatim out
of that repo's own `tokenizer_config.json` (key `chat_template`). Not authored
here and not modified -- extracting it is a transport step, not a change of
regime.

It has to be passed to vLLM with `--chat-template` because transformers 5.x no
longer picks a template up from `tokenizer_config.json`; it reads a separate
`chat_template.jinja`, which this model's repo predates. Without it every
request fails with "As of transformers v4.44, default chat template is no
longer allowed", which looks like a tool-parser fault but is not: all three
candidate parsers (mistral, hermes, pythonic) fail identically, at prompt
construction, before the model ever emits a token.
