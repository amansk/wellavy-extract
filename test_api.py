import requests
import sys

def test_health():
    response = requests.get("http://localhost:8000/")
    print("Health check response:", response.json())

def test_pdf_conversion(pdf_path):
    url = "http://localhost:8000/convert"
    files = {"file": open(pdf_path, "rb")}
    
    print(f"Sending {pdf_path} for conversion...")
    response = requests.post(url, files=files)
    
    if response.status_code == 200:
        output_file = "output.csv"
        with open(output_file, "wb") as f:
            f.write(response.content)
        print(f"Success! CSV saved as {output_file}")
    else:
        print("Error:", response.json())

if __name__ == "__main__":
    test_health()
    
    if len(sys.argv) > 1:
        test_pdf_conversion(sys.argv[1])
    else:
        print("Please provide a PDF file path as argument")
        print("Usage: python test_api.py path/to/your/file.pdf") 