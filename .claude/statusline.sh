#!/usr/bin/env bash
# Status line: context window fill bar, e.g.  [████████░░░░░░░░░░░░] 40%
# Claude Code pipes a JSON blob with session info to stdin on every update.

input=$(cat)

# Prefer the percentage Claude Code computes; fall back to summing current_usage.
pct=$(jq -r '
  .context_window as $c
  | if $c.used_percentage != null then $c.used_percentage
    elif ($c.context_window_size // 0) > 0 and $c.current_usage != null then
      (($c.current_usage.input_tokens // 0)
       + ($c.current_usage.cache_creation_input_tokens // 0)
       + ($c.current_usage.cache_read_input_tokens // 0)) * 100 / $c.context_window_size
    else 0 end
  | floor' <<<"$input" 2>/dev/null)
pct=${pct:-0}
(( pct < 0 )) && pct=0
(( pct > 100 )) && pct=100

model=$(jq -r '.model.display_name // empty' <<<"$input" 2>/dev/null)

width=20
filled=$(( pct * width / 100 ))
bar=""
for ((i = 0; i < width; i++)); do
  if (( i < filled )); then bar+="█"; else bar+="░"; fi
done

# green < 50%, yellow < 80%, red otherwise
if   (( pct < 50 )); then color=$'\033[32m'
elif (( pct < 80 )); then color=$'\033[33m'
else                      color=$'\033[31m'
fi
reset=$'\033[0m'

printf '%s[%s] %d%%%s' "$color" "$bar" "$pct" "$reset"
[[ -n $model ]] && printf ' · %s' "$model"
printf '\n'
