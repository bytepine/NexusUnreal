"""
Phase 3: Migrate FNexusCapability::Execute to return FCapabilityResult.

Strategy (lambda-wrapper adapter):
  - Headers: Replace 4-param Execute declaration → 1-param
  - Cpp files: Wrap existing Execute body in a lambda, add FCapabilityResult adapter
"""

import re
import os
import glob

CAP_ROOT = os.path.join(os.path.dirname(__file__), os.pardir,
    "Plugins", "Developer", "NexusLink", "Source", "NexusLink",
    "Private", "Capabilities")
CAP_ROOT = os.path.normpath(CAP_ROOT)

# ── Header transformation ─────────────────────────────────────────────────────

OLD_DECL_PATTERN = re.compile(
    r'\tvirtual void Execute\(const TSharedPtr<FJsonObject>& Arguments,\s*\n'
    r'\t\s+TArray<TSharedPtr<FJsonValue>>& OutEntries,\s*\n'
    r'\t\s+TSharedPtr<FJsonObject>& OutTop,\s*\n'
    r'\t\s+FString& OutError\) const override;',
    re.MULTILINE
)
NEW_DECL = '\tvirtual FCapabilityResult Execute(const TSharedPtr<FJsonObject>& Arguments) const override;'


def transform_header(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    if 'void Execute(const TSharedPtr<FJsonObject>& Arguments,' not in content:
        return False
    new_content = OLD_DECL_PATTERN.sub(NEW_DECL, content)
    if new_content == content:
        print(f"  [WARN] Header pattern not matched: {os.path.basename(path)}")
        return False
    with open(path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print(f"  [H] {os.path.basename(path)}")
    return True


# ── Cpp transformation ────────────────────────────────────────────────────────

# Matches the Execute function definition (4-param, optional /*OutTop*/ comment)
EXEC_DEF_PATTERN = re.compile(
    r'(void\s+\w+::Execute\(const TSharedPtr<FJsonObject>& Arguments,\s*\n'
    r'(?:.*?)TArray<TSharedPtr<FJsonValue>>& OutEntries,\s*\n'
    r'(?:.*?)TSharedPtr<FJsonObject>& (?:/\*OutTop\*/)?\s*(?:OutTop)?,\s*\n'
    r'(?:.*?)FString& OutError\) const\s*\n)',
    re.MULTILINE | re.DOTALL
)

def find_function_body(text, start_pos):
    """
    Find the matching closing brace of a function starting at `start_pos`
    (which should point to the '{' that opens the function body).
    Returns (body_start, body_end) where body_end is the position just after the closing '}'.
    """
    brace_count = 0
    i = start_pos
    body_start = -1
    while i < len(text):
        ch = text[i]
        if ch == '{':
            brace_count += 1
            if body_start == -1:
                body_start = i
        elif ch == '}':
            brace_count -= 1
            if brace_count == 0:
                return (body_start, i + 1)
        elif ch == '/' and i + 1 < len(text):
            # Skip line comment
            if text[i+1] == '/':
                while i < len(text) and text[i] != '\n':
                    i += 1
                continue
            # Skip block comment
            elif text[i+1] == '*':
                i += 2
                while i < len(text) - 1:
                    if text[i] == '*' and text[i+1] == '/':
                        i += 2
                        break
                    i += 1
                continue
        elif ch == '"':
            # Skip string literal
            i += 1
            while i < len(text) and text[i] != '"':
                if text[i] == '\\':
                    i += 1
                i += 1
        i += 1
    return (-1, -1)


def extract_class_name(sig_text):
    """Extract 'FXxxCapability' from 'void FXxxCapability::Execute(...'"""
    m = re.search(r'void\s+(\w+)::Execute', sig_text)
    return m.group(1) if m else 'Unknown'


WRAPPER_INTRO = """\tFCapabilityResult _R;
\tTSharedPtr<FJsonObject> _Top = MakeShared<FJsonObject>();
\t[&](TArray<TSharedPtr<FJsonValue>>& OutEntries,
\t    TSharedPtr<FJsonObject>& OutTop,
\t    FString& OutError)
\t{"""

WRAPPER_OUTRO = """\t}(_R.Entries, _Top, _R.FatalError);
\tif (_Top->Values.Num() > 0) { _R.TopFields = _Top; }
\treturn _R;
"""


def transform_cpp(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    if '::Execute(' not in content:
        return False

    # Find Execute definition signature
    m = EXEC_DEF_PATTERN.search(content)
    if not m:
        print(f"  [WARN] Cpp signature pattern not matched: {os.path.basename(path)}")
        # Try to show what we have
        idx = content.find('::Execute(')
        if idx != -1:
            print(f"    Found at: {repr(content[idx-20:idx+200])}")
        return False

    class_name = extract_class_name(m.group(0))
    new_sig = f"FCapabilityResult {class_name}::Execute(const TSharedPtr<FJsonObject>& Arguments) const\n"

    # Find the function body
    body_start_search = m.end()
    body_start, body_end = find_function_body(content, body_start_search)
    if body_start == -1:
        print(f"  [WARN] Could not find Execute body in: {os.path.basename(path)}")
        return False

    # Extract original body (between { and })
    original_body = content[body_start + 1 : body_end - 1]  # strip outer braces

    # Indent the original body by one extra tab (to be inside the lambda)
    indented_body = '\t' + original_body.replace('\n', '\n\t')
    # Remove trailing whitespace from the added indent on empty lines
    indented_body = re.sub(r'\t+\n', '\n', indented_body)

    new_body = '\n' + WRAPPER_INTRO + '\n' + indented_body + '\n' + WRAPPER_OUTRO

    new_content = (
        content[:m.start()] +
        new_sig +
        '{\n' +
        new_body +
        '}\n' +
        content[body_end:]
    )

    with open(path, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"  [C] {os.path.basename(path)}")
    return True


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    print(f"Scanning: {CAP_ROOT}")

    headers = glob.glob(os.path.join(CAP_ROOT, "**", "*.h"), recursive=True)
    cpps    = glob.glob(os.path.join(CAP_ROOT, "**", "*.cpp"), recursive=True)

    print(f"\n--- Headers ({len(headers)}) ---")
    h_ok = sum(1 for p in sorted(headers) if transform_header(p))

    print(f"\n--- Cpp ({len(cpps)}) ---")
    c_ok = sum(1 for p in sorted(cpps) if transform_cpp(p))

    print(f"\nDone: {h_ok}/{len(headers)} headers, {c_ok}/{len(cpps)} cpps transformed.")


if __name__ == "__main__":
    run()
