import sys
import os
import argparse
from src.gui import run_app
from src.processing import PDFProcessor
from src.utils import load_config

def parse_metadata_args(args):
    """Parse --remove-meta, --edit-meta, and --custom-meta CLI args."""
    remove_vars = {}
    edit_vars = {}
    custom_metadata = []
    if args.remove_meta:
        for key in args.remove_meta:
            remove_vars[key] = type('Var', (), {'get': lambda self=True: True})()
            edit_vars[key] = type('Var', (), {'get': lambda self: ''})()
    if args.edit_meta:
        for pair in args.edit_meta:
            if '=' in pair:
                key, value = pair.split('=', 1)
                remove_vars[key] = type('Var', (), {'get': lambda self=True: False})()
                edit_vars[key] = type('Var', (), {'get': lambda self, v=value: v})()
    if args.custom_meta:
        for pair in args.custom_meta:
            if '=' in pair:
                key, value = pair.split('=', 1)
                remove_var = type('Var', (), {'get': lambda self=True: False})()
                value_var = type('Var', (), {'get': lambda self, v=value: v})()
                custom_metadata.append((remove_var, key, value_var))
    return remove_vars, edit_vars, custom_metadata

def collect_pdf_files_cli(paths, recursive, max_depth):
    pdfs = []
    for path in paths:
        if os.path.isfile(path) and path.lower().endswith('.pdf'):
            pdfs.append(path)
        elif os.path.isdir(path):
            for root, dirs, files in os.walk(path):
                if recursive and max_depth > 0:
                    depth = root.replace(path, '').count(os.sep)
                    if depth > max_depth:
                        continue
                for file in files:
                    if file.lower().endswith('.pdf'):
                        pdfs.append(os.path.join(root, file))
    return list(set(pdfs))

def main():
    parser = argparse.ArgumentParser(description="Advanced PDF Metadata Remover (GUI & CLI)")
    parser.add_argument('--cli', action='store_true', help='Run in CLI mode')
    parser.add_argument('inputs', nargs='*', help='PDF files or folders to process (CLI mode)')
    parser.add_argument('--output', help='Output directory (CLI mode)')
    parser.add_argument('--overwrite', action='store_true', help='Overwrite original files (CLI mode)')
    parser.add_argument('--backup', action='store_true', help='Backup originals before overwrite (CLI mode)')
    parser.add_argument('--recursive', action='store_true', help='Recursively process folders (CLI mode)')
    parser.add_argument('--max-depth', type=int, default=3, help='Max recursion depth (CLI mode)')
    parser.add_argument('--compression', choices=['None', 'Low', 'Medium', 'High', 'Maximum'], default='None', help='Compression level (CLI mode)')
    parser.add_argument('--remove-meta', nargs='*', help='Metadata fields to remove (e.g. --remove-meta /Author /Title)')
    parser.add_argument('--edit-meta', nargs='*', help='Metadata fields to edit (e.g. --edit-meta /Author=Anon /Title=Doc)')
    parser.add_argument('--custom-meta', nargs='*', help='Custom metadata fields (e.g. --custom-meta /MyField=Value)')
    args = parser.parse_args()

    if args.cli:
        # File existence check
        missing = [p for p in args.inputs if not os.path.exists(p)]
        if missing:
            print("Error: The following input files/folders do not exist:")
            for m in missing:
                print(f"  {m}")
            sys.exit(1)
        if not args.inputs:
            print("Usage: python main.py --cli input.pdf [input2.pdf ...] [--output DIR] [--overwrite] [--backup] [--recursive] [--max-depth N] [--compression LEVEL] [--remove-meta ...] [--edit-meta ...] [--custom-meta ...]")
            sys.exit(1)
        config = load_config('pdf_remover_config.json')
        config['backup'] = args.backup
        config['overwrite'] = args.overwrite
        config['recursive'] = args.recursive
        config['max_depth'] = args.max_depth
        processor = PDFProcessor(config)
        remove_vars, edit_vars, custom_metadata = parse_metadata_args(args)
        pdf_files = collect_pdf_files_cli(args.inputs, args.recursive, args.max_depth)
        if not pdf_files:
            print("No PDF files found.")
            sys.exit(1)
        print(f"Found {len(pdf_files)} PDF file(s) to process.")
        success_count = 0
        error_count = 0
        compression_increase_count = 0
        for pdf_path in pdf_files:
            if args.overwrite:
                output_path = pdf_path
            elif args.output:
                if os.path.isdir(args.output):
                    filename = os.path.basename(pdf_path)
                    output_path = os.path.join(args.output, filename)
                else:
                    output_path = args.output
            else:
                base, ext = os.path.splitext(pdf_path)
                output_path = f"{base}_clean{ext}"
            result = processor.process_single_file(
                pdf_path,
                output_path,
                remove_vars,
                edit_vars,
                custom_metadata,
                args.compression
            )
            if result is True:
                print(f"Processed: {pdf_path} -> {output_path}")
                success_count += 1
            elif result == "compression_increase":
                print(f"Processed (larger after compression): {pdf_path} -> {output_path}")
                success_count += 1
                compression_increase_count += 1
            else:
                print(f"Error processing: {pdf_path}")
                error_count += 1
        print(f"\nSummary: Success: {success_count}, Errors: {error_count}, Files with increased size after compression: {compression_increase_count}")
        sys.exit(0 if error_count == 0 else 1)
    else:
        run_app()

if __name__ == "__main__":
    main() 