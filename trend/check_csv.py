import csv
import sys
if __name__ == '__main__':

    # 指定要检查的CSV文件路径
    if len(sys.argv) > 1:
        csv_file = sys.argv[1]
    else:
        csv_file = '/Users/bytedance/pythonProject/cryptotrade/data/ETH/ethusdt_1d_20250101_20251222.csv'

    try:
        with open(csv_file, 'r') as f:
            reader = csv.reader(f)
            headers = next(reader)
            print(f"CSV表头: {headers}")
            print(f"表头列数: {len(headers)}")

            # 检查数据行
            row_count = 1
            error_rows = []

            for row in reader:
                row_count += 1
                if len(row) != 6:
                    error_rows.append((row_count, len(row), row))

            print(f"\n总数据行数: {row_count - 1}")

            if error_rows:
                print(f"\n发现{len(error_rows)}行数据列数不正确:")
                for line_num, col_count, row_content in error_rows:
                    print(f"第{line_num}行: {col_count}列")
                    print(f"  内容: {row_content}")
            else:
                print("\n所有数据行格式正确，都包含6列数据")

    except Exception as e:
        print(f"检查CSV文件时出错: {e}")