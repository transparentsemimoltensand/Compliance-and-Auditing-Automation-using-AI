# run_chunk.py - Test semantic chunking on cleaned.txt
import chunking
import json
import sys

def test_chunking(input_file="cleaned.txt", output_file="chunks.json"):
    """Test semantic chunking on cleaned BMR file."""
    try:
        # Read cleaned text
        content = chunking.read_bmr_file(input_file)
        print(f"Read {len(content.splitlines())} lines from {input_file}")
        
        # Apply semantic chunking (uses DEFAULT_CHUNKING_CONFIG)
        chunks = chunking.semantic_chunk_bmr(content)
        
        # Save chunks to JSON
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(chunks, f, indent=2, ensure_ascii=False)
        
        print(f"\nGenerated {len(chunks)} semantic chunks")
        print(f"Saved to {output_file}")
        
        # Show chunk statistics
        total_lines = sum(len(chunk.splitlines()) for chunk in chunks)
        avg_lines = total_lines / len(chunks) if chunks else 0
        print(f"Average lines per chunk: {avg_lines:.1f}")
        
        # Preview first 3 chunks
        print("\n--- First 3 chunks preview ---")
        for i, chunk in enumerate(chunks[:3]):
            lines = chunk.splitlines()
            print(f"Chunk {i+1}: {len(lines)} lines")
            print(chunk[:150] + "..." if len(chunk) > 150 else chunk)
            print()
            
    except Exception as e:
        print(f"Error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    # Optional: take input file as argument
    input_file = sys.argv[1] if len(sys.argv) > 1 else "cleaned.txt"
    output_file = sys.argv[2] if len(sys.argv) > 2 else "chunks.json"
    
    test_chunking(input_file, output_file)