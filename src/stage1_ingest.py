import glob     # to handle file patterns
import os
import pandas as pd

def parse_iaga_file (filepath: str, station_id: str) -> pd.DataFrame: # DataFrame: to indicate return type
    """
    Parse one IAGA-2002 daily file into a DataFrame.
    NOTE: IAGA files vary slightly. We will adjust parsing once we see the column layout.
    """
    # Mani IAGA files have header lines before the data starts
    # A common pattern: data lines start after a line with 'DATE' in it
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    
    # Find header line index (first line that contains 'DATE' and 'TIME')
    header_idx = None
    for i, line in enumerate(lines):
        if 'DATE' in line and 'TIME' in line:
            header_idx = i
            break
    if header_idx is None:
        raise ValueError(f"Could not find data header in {filepath}")
    
    # Read from header line onward using whitespace separator
    from io import StringIO # to read from string buffer
    data_str = "".join(lines[header_idx:]) # join lines from header onward
    df = pd.read_csv(StringIO(data_str), sep=r"\s+", engine='python')   # use regex for whitespace separator
    # Note: regex: r"\s+" matches one or more whitespace characters
    
    # Common columns: DATE, TIME, X, Y, Z (or H, D, Z)
    # Create timestamp
    df["timestamp_utc"] = pd.to_datetime(df["DATE"] + " " + df["TIME"], utc= True)  # combine DATE and TIME into timestamp
    
    # --- Select exactly ONE X/Y/Z column (prevents duplicate names) ---

    # Prefer the station-prefixed component names like BOUX, BOUY, BOUZ
    xcol = f"{station_id}X"
    ycol = f"{station_id}Y"
    zcol = f"{station_id}Z"

    # Some files may use lowercase headers
    cols_upper = {c.upper(): c for c in df.columns}

    xcol_actual = cols_upper.get(xcol.upper())
    ycol_actual = cols_upper.get(ycol.upper())
    zcol_actual = cols_upper.get(zcol.upper())

    if not (xcol_actual and ycol_actual and zcol_actual):
        raise ValueError(
            f"Could not find expected component columns {xcol},{ycol},{zcol} in {df.columns.tolist()}"
        )

    # Build a clean dataframe with only what we need
    clean = pd.DataFrame({
        "station_id": station_id,
        "timestamp_utc": df["timestamp_utc"],
        "X": pd.to_numeric(df[xcol_actual], errors="coerce"),
        "Y": pd.to_numeric(df[ycol_actual], errors="coerce"),
        "Z": pd.to_numeric(df[zcol_actual], errors="coerce"),
    })

    # Remove bad rows
    clean = clean.dropna(subset=["timestamp_utc"])
    clean = clean.dropna(subset=["X", "Y", "Z"], how="any")

    return clean
    
def main():
    station_id = "BOU" # Station identifier
    input_dir = "data/raw_iaga/"  # Directory containing IAGA files
    out_path = f"data/processed/raw_minute/{station_id}_raw_minute.parquet"  # Output file path
    os.makedirs(os.path.dirname(out_path), exist_ok=True)  # Ensure output directory exists
    
    files = sorted(glob.glob(os.path.join(input_dir, "*"))) # Get list of all files in input directory
    if not files:
        raise FileNotFoundError(f"No files found in {input_dir}")
    
    frames = []
    for fp in files:
        try:
            df_one = parse_iaga_file(fp, station_id)
            if df_one is None or df_one.empty:
                print(f"[SKIP] Parsed empty/None: {fp}")
                continue
            print(f"[OK] {os.path.basename(fp)} -> {len(df_one)} rows, columns={df_one.columns.tolist()}")
            frames.append(df_one)
        except Exception as e:
            print(f"[FAIL] {fp}: {type(e).__name__}: {e}")
            continue
        
    if not frames:
        raise RuntimeError("No files were parsed successfully. Check header detection / file format.")
    
    df = pd.concat(frames, ignore_index=True)  # Concatenate all DataFrames
    
    df.to_parquet(out_path, index=False)  # Save to Parquet file
    print(f"Saved {len(df):,} rows to {out_path}") 
    
if __name__ == "__main__":
    main()