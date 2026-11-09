from pathlib import Path
import pandas as pd
from db import get_engine
 
OUTPUT_PATH = Path(__file__).resolve().parent / "data" / "calls_raw.csv"
 
 
def main():
    engine = get_engine()
    query = """
        SELECT
            c.call_id, c.campaign_id, c.customer_id, c.employee_id,
            c.start_time, c.end_time, c.duration,
            r.result_code
        FROM calls c
        LEFT JOIN call_results r ON r.result_id = c.result_id
        ORDER BY c.start_time
    """
    df = pd.read_sql(query, engine, parse_dates=["start_time", "end_time"])
 
    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)
 
    print(f"Đã lưu {len(df):,} dòng vào {OUTPUT_PATH}")
    print(f"Từ {df.start_time.min()} đến {df.start_time.max()}")
 
 
if __name__ == "__main__":
    main()