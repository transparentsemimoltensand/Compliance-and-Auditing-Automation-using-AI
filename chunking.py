import re

# Default semantic chunking configuration (from Gemini analysis)
DEFAULT_CHUNKING_CONFIG = {
    "primary_separators": [
        r"(?m)^GSK::",
        r"(?m)^Dispensing:$",
        r"(?m)^Sifting:$",
        r"(?m)^Blending:$",
        r"(?m)^Compression.*:$",
        r"(?m)^Coating:$",
        r"(?m)^Primary Packing:$",
        r"(?m)^Yield Summary:$",
        r"(?m)^Issuance Details:$",
        r"(?m)^Compression Completed on::$",
        r"(?m)^Tablets::$"
    ],
    "secondary_separators": [
        r"(?m)^Activity:",
        r"(?m)^Instructions:",
        r"(?m)^Ingredient:",
        r"(?m)^Equipment Name:",
        r"(?m)^Parameter:",
        r"(?m)^Time \|",
        r"(?m)^Tablets::",
        r"(?m)^Check\*::"
    ],
    "line_grouping_rules": {
        "strategy": "Lookahead",
        "continuation_indicators": [
            r"^\s*\d+(\.\d+)?.*$",
            r"^\s*Observation:",
            r"^\s*Spec:",
            r"^\s*Range:",
            r"^\s*Col_\d+:"
        ]
    },
    "max_lines_per_chunk": 60,
    
    # Table detection and formatting rules
    "table_config": {
        "start_markers": [
            r"(?m)^\s*Station:\s*Spec",
            r"(?m)^\s*Time\s*\|\s*Activity",
            r"(?m)^\s*Col_\d+:",
            r"(?m)^\s*Equipment Name\s*\|\s*Equipment ID",
            r"(?m)^\s*Ingredient:\s*.*Spec:",
            r"(?m)^\s*Friability Observations\s*\|\s*Disintegration Time",
            r"(?m)^\s*No\.?\s*\|\s*Instructions"
        ],
        "end_markers": [
            r"(?m)^\s*Prepared By QA:",
            r"(?m)^\s*GSK::",
            r"(?m)^\s*Average\s*Weight",
            r"(?m)^\s*Done and\s*\|",
            r"(?m)^\s*Range\s*\|",
            r"(?m)^\s*::\s*$"
        ],
        "row_indicators": [
            r"(?m)^\s*Station:\s*\d+",
            r"(?m)^\s*Activity:\s*\w+",
            r"(?m)^\s*\d{1,2}\.\d{2}\s*(am|pm)",
            r"(?m)^\s*Ingredient:\s*[A-Z]",
            r"(?m)^\s*Length:\s*\d+\.\d+"
        ],
        "max_rows_per_chunk": 12,
        "min_rows_per_chunk": 3,
        "header_propagation": True
    }
}

def read_bmr_file(file_path):
    """Read the content of a BMR text file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        raise
    except Exception as e:
        print(f"Error reading file '{file_path}': {e}")
        raise

def chunk_bmr(content, lines_per_chunk=500):
    """Chunk the BMR content into segments of specified line count."""
    lines = content.splitlines()
    chunks = [lines[i:i + lines_per_chunk] for i in range(0, len(lines), lines_per_chunk)]
    return ['\n'.join(chunk) for chunk in chunks]

def semantic_chunk_bmr(content, config=None):
    """Chunk BMR content using semantic boundaries with in-place table formatting."""
    if config is None:
        config = DEFAULT_CHUNKING_CONFIG
    
    # Convert tables to Markdown format IN PLACE (no extraction)
    content = convert_tables_to_markdown(content, config)
    
    # Apply semantic chunking to the formatted content
    return semantic_chunk_bmr_basic(content, config)

def convert_tables_to_markdown(text, config):
    """Convert detected tables to Markdown format while keeping them in-place."""
    lines = text.splitlines()
    result_lines = []
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Check if this line starts a table
        if is_table_start(line, config["table_config"]["start_markers"]):
            # Find the full table
            table_lines, next_index = extract_table_lines(lines, i, config["table_config"])
            
            # Convert table to Markdown format
            markdown_tables = convert_table_to_markdown(table_lines, config["table_config"])
            
            # Add Markdown tables to result (in-place replacement)
            result_lines.extend(markdown_tables)
            i = next_index
        else:
            result_lines.append(line)
            i += 1
    
    return '\n'.join(result_lines)

def is_table_start(line, start_markers):
    """Check if line indicates the start of a table."""
    for pattern in start_markers:
        if re.search(pattern, line):
            return True
    return False

def extract_table_lines(lines, start_idx, table_config):
    """Extract consecutive lines that belong to the same table."""
    table_lines = []
    i = start_idx
    
    while i < len(lines):
        line = lines[i]
        
        # Check if line marks the end of a table
        is_end = False
        for pattern in table_config["end_markers"]:
            if re.search(pattern, line):
                is_end = True
                break
        
        if is_end and i > start_idx:
            break
        
        # Check if line is part of a table row
        is_table_row = False
        for pattern in table_config["row_indicators"]:
            if re.search(pattern, line):
                is_table_row = True
                break
        
        # Add line if it's part of the table
        if i == start_idx or is_table_row or (line.strip() and i - start_idx < 3):
            table_lines.append(line)
        else:
            # Check if next lines are also not table rows
            lookahead_table = False
            for j in range(i, min(i + 2, len(lines))):
                for pattern in table_config["row_indicators"]:
                    if re.search(pattern, lines[j]):
                        lookahead_table = True
                        break
                if lookahead_table:
                    break
            
            if not lookahead_table:
                break
            else:
                table_lines.append(line)
        
        i += 1
    
    return table_lines, i

def convert_table_to_markdown(table_lines, table_config):
    """Convert table lines to Markdown format with safe splitting for large tables."""
    if not table_lines:
        return []
    
    # If table is small enough, format as single Markdown table
    if len(table_lines) <= table_config["max_rows_per_chunk"]:
        markdown_table = format_as_markdown(table_lines)
        return [markdown_table] if markdown_table else []
    
    # For large tables: split with repeated headers
    return split_and_format_large_table(table_lines, table_config)

def format_as_markdown(table_lines):
    """Format table lines as a proper Markdown table with headers."""
    if len(table_lines) < 2:
        return '\n'.join(table_lines)
    
    # Check if already formatted as Markdown
    if table_lines[0].strip().startswith('|') and len(table_lines) > 1 and '---' in table_lines[1]:
        return '\n'.join(table_lines)
    
    # Convert to Markdown
    header = table_lines[0]
    pipe_count = header.count('|')
    columns = pipe_count + 1 if pipe_count > 0 else len(header.split())
    
    markdown_lines = []
    markdown_lines.append(f"| {header} |")
    markdown_lines.append("| " + " | ".join(["---"] * columns) + " |")
    
    for row in table_lines[1:]:
        if row.strip():
            markdown_lines.append(f"| {row} |")
    
    return '\n'.join(markdown_lines)

def detect_columns(table_lines):
    """Detect number of columns in a table."""
    if not table_lines:
        return 0
    
    # Count pipe separators in first few rows
    column_counts = []
    for i in range(min(3, len(table_lines))):
        line = table_lines[i]
        pipes = line.count('|')
        column_counts.append(pipes + 1)  # n pipes = n+1 columns
    
    # Return most common column count
    if column_counts:
        return max(set(column_counts), key=column_counts.count)
    return 0


def split_and_format_large_table(table_lines, table_config):
    """Split large table with PROPER header propagation (Gemini's fix)."""
    if not table_lines or len(table_lines) < 2:
        return ['\n'.join(table_lines)] if table_lines else []
    
    # STEP 1: Convert to proper Markdown if not already
    formatted_lines = []
    
    # Check if already Markdown
    if table_lines[0].strip().startswith('|'):
        formatted_lines = table_lines
    else:
        # Convert plain text to Markdown
        header = table_lines[0]
        pipe_count = header.count('|')
        columns = pipe_count + 1 if pipe_count > 0 else len(header.split())
        
        formatted_lines.append(f"| {header} |")
        formatted_lines.append("| " + " | ".join(["---"] * columns) + " |")
        formatted_lines.extend([f"| {row} |" for row in table_lines[1:] if row.strip()])
    
    # STEP 2: Group by COMPLETE Station records
    # Find rows that start new Station records
    station_rows = []
    current_group = []
    
    for i, line in enumerate(formatted_lines):
        current_group.append(line)
        
        # Check if this is a Station boundary
        is_station_boundary = (
            'Station:' in line or 
            line.strip().startswith('| Station:') or
            (i < len(formatted_lines) - 1 and 'Station:' in formatted_lines[i + 1])
        )
        
        # Also check if next line starts new logical row
        if is_station_boundary and len(current_group) > 1:
            # Don't include the boundary in current group
            station_rows.append(current_group[:-1])
            current_group = [line]
    
    if current_group:
        station_rows.append(current_group)
    
    # STEP 3: Split with header propagation
    result_tables = []
    max_rows = table_config.get("max_rows_per_chunk", 12)
    
    current_chunk = []
    current_row_count = 0
    
    for group in station_rows:
        if current_row_count + len(group) > max_rows and current_row_count > 0:
            # Finalize current chunk
            result_tables.append('\n'.join(current_chunk))
            current_chunk = []
            current_row_count = 0
        
        # Add group to chunk
        current_chunk.extend(group)
        current_row_count += len(group)
    
    # Add final chunk
    if current_chunk:
        result_tables.append('\n'.join(current_chunk))
    
    # STEP 4: Apply Gemini's header propagation rule
    if len(result_tables) > 1 and table_config.get("header_propagation", True):
        # Extract headers from first table
        first_table_lines = result_tables[0].split('\n')
        headers = []
        
        # Find header rows (first lines until separator)
        for line in first_table_lines:
            headers.append(line)
            if '---' in line or line.count('|') >= 2:
                break
        
        header_block = '\n'.join(headers)
        
        # Add to continuation chunks
        final_tables = [result_tables[0]]  # Keep first table as-is
        
        for i in range(1, len(result_tables)):
            continued_table = "**[Table Continued from Previous Section]**\n" + header_block + "\n" + result_tables[i]
            final_tables.append(continued_table)
        
        return final_tables
    
    return result_tables


def semantic_chunk_bmr_basic(content, config):
    """Apply semantic chunking to content (tables already formatted)."""
    lines = content.splitlines()
    chunks = []
    current_chunk = []
    
    for i, line in enumerate(lines):
        if is_boundary(line, config["primary_separators"]):
            if current_chunk:
                chunks.append('\n'.join(current_chunk))
                current_chunk = []
        
        grouped_line = apply_grouping_rules(line, lines, i, config["line_grouping_rules"])
        if grouped_line is not None:
            current_chunk.append(grouped_line)
    
    if current_chunk:
        chunks.append('\n'.join(current_chunk))
    
    chunks = split_oversized_chunks(chunks, config)
    chunks = prevent_orphan_chunks(chunks, config)
    
    return chunks

def is_boundary(line, patterns):
    """Check if line matches any boundary pattern."""
    for pattern in patterns:
        if re.search(pattern, line):
            return True
    return False

def apply_grouping_rules(line, lines, i, rules):
    """Apply line grouping rules for multi-line values."""
    if i > 0 and is_continuation_line(line, rules["continuation_indicators"]):
        return None
    
    if i + 1 < len(lines) and is_continuation_line(lines[i + 1], rules["continuation_indicators"]):
        merged = line
        j = i + 1
        while j < len(lines) and is_continuation_line(lines[j], rules["continuation_indicators"]):
            merged += " " + lines[j].strip()
            j += 1
        return merged
    
    return line

def is_continuation_line(line, indicators):
    """Check if line is a continuation of previous line."""
    line_stripped = line.strip()
    
    if not line_stripped:
        return False
    
    for pattern in indicators:
        if re.search(pattern, line_stripped):
            return True
    
    key_patterns = [r'^[A-Za-z][A-Za-z ]+[|:]', r'^[A-Z][a-z]+:$']
    for pattern in key_patterns:
        if re.search(pattern, line_stripped):
            return False
    
    return True

def split_oversized_chunks(chunks, config):
    """Split chunks that exceed size limits."""
    result = []
    max_lines = config.get("max_lines_per_chunk", 60)
    
    for chunk in chunks:
        lines = chunk.split('\n')
        
        if len(lines) <= max_lines:
            result.append(chunk)
            continue
        
        # Try to split at secondary boundaries first
        subchunks = []
        current_subchunk = []
        
        for line in lines:
            current_subchunk.append(line)
            
            if (len(current_subchunk) >= 20 and 
                is_boundary(line, config["secondary_separators"])):
                subchunks.append('\n'.join(current_subchunk))
                current_subchunk = []
        
        if current_subchunk:
            subchunks.append('\n'.join(current_subchunk))
        
        # If still oversized, use simple line splitting
        for subchunk in subchunks:
            sub_lines = subchunk.split('\n')
            if len(sub_lines) > max_lines:
                for i in range(0, len(sub_lines), max_lines):
                    result.append('\n'.join(sub_lines[i:i + max_lines]))
            else:
                result.append(subchunk)
    
    return result

def prevent_orphan_chunks(chunks, config, min_lines=5):
    """Merge small orphan chunks with neighbors."""
    if len(chunks) <= 1:
        return chunks
    
    merged = []
    i = 0
    
    while i < len(chunks):
        current = chunks[i]
        current_lines = current.splitlines()
        
        # Skip if it's a table (starts with pipe)
        is_table = current.strip().startswith('|')
        
        if not is_table and len(current_lines) < min_lines:
            # Try to merge with previous chunk
            if merged and not is_table_chunk(merged[-1]):
                last_chunk = merged.pop()
                merged.append(last_chunk + "\n" + current)
            # Or merge with next chunk
            elif i + 1 < len(chunks) and not is_table_chunk(chunks[i + 1]):
                next_chunk = chunks[i + 1]
                merged.append(current + "\n" + next_chunk)
                i += 1
            else:
                merged.append(current)
        else:
            merged.append(current)
        
        i += 1
    
    return merged

def is_table_chunk(chunk):
    """Check if chunk is a Markdown table."""
    lines = chunk.splitlines()
    if len(lines) >= 2:
        # Check if first line starts with pipe and second line has --- separators
        return (lines[0].strip().startswith('|') and 
                '---' in lines[1] and '|' in lines[1])
    return False