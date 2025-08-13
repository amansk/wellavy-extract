# Blood Test PDF Extractor API Documentation

## Overview

This API provides two main services:
1. **Pattern-based extraction** - Fast extraction using regex patterns for known lab formats
2. **AI-powered extraction** - Uses Claude AI for intelligent extraction from any PDF format

## Base URL

```
Production: https://your-app.railway.app
Local: http://localhost:8000
```

## Authentication

The AI extraction endpoint requires API key authentication to prevent unauthorized usage and control costs.

### Setting up Authentication

**For Railway Deployment:**
1. Go to your Railway project dashboard
2. Navigate to Variables section
3. Add: `API_SECRET_KEY=your-secure-random-key-here`
4. Add: `ANTHROPIC_API_KEY=sk-ant-your-claude-key`

**For Local Development:**
1. Copy `.env.example` to `.env.local`
2. Set your API keys in the file
3. The application will load these automatically

### Making Authenticated Requests

Include the API key in the request header:
```
X-API-Key: your-api-key-here
```

---

## Endpoints

### 1. Health Check

**GET** `/`

Check if the API is running.

**Response:**
```json
{
  "status": "healthy",
  "message": "PDF to CSV Converter API is running"
}
```

---

### 2. Pattern-Based Extraction (Public)

**POST** `/convert`

Extract blood test data using pattern matching. No authentication required.

**Request:**
- **Method:** POST
- **Content-Type:** multipart/form-data
- **Body:** PDF file

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `include_ranges` | boolean | false | Include reference ranges in output |
| `format` | string | auto | Force specific format: 'quest', 'labcorp', 'function_health' |

**Response:**
- **Content-Type:** text/csv
- **Body:** CSV file download

**Example:**
```bash
curl -X POST "http://localhost:8000/convert?include_ranges=true" \
  -F "file=@blood_test.pdf" \
  -o results.csv
```

---

### 3. AI-Powered Extraction (Secured)

**POST** `/api/v1/ai-extract`

Extract blood test data using Claude AI. Requires authentication.

**Request:**
- **Method:** POST
- **Headers:** 
  - `X-API-Key: your-api-key`
- **Content-Type:** multipart/form-data
- **Body:** PDF file

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `include_ranges` | boolean | false | Include reference ranges in output |

**Response:**
```json
{
  "success": true,
  "test_date": "2024-01-15",
  "marker_count": 85,
  "results": [
    {
      "marker": "Glucose",
      "value": "95",
      "min_range": "70",    // Only if include_ranges=true
      "max_range": "100"     // Only if include_ranges=true
    },
    {
      "marker": "Cholesterol",
      "value": "180",
      "min_range": null,
      "max_range": "200"
    }
  ]
}
```

**Error Responses:**

| Status Code | Description | Response |
|------------|-------------|----------|
| 401 | Unauthorized | `{"detail": "Invalid API key"}` |
| 400 | Bad Request | `{"detail": "File must be a PDF"}` |
| 400 | No Data | `{"detail": "No valid data could be extracted from the PDF"}` |
| 500 | Server Error | `{"detail": "Error processing PDF: [error message]"}` |

---

## Code Examples

### Python

```python
import requests
import json

class BloodTestExtractor:
    def __init__(self, api_url, api_key):
        self.api_url = api_url
        self.api_key = api_key
    
    def extract_with_ai(self, pdf_path, include_ranges=False):
        """Extract blood test results using AI."""
        url = f"{self.api_url}/api/v1/ai-extract"
        headers = {"X-API-Key": self.api_key}
        params = {"include_ranges": include_ranges}
        
        with open(pdf_path, 'rb') as f:
            files = {'file': ('blood_test.pdf', f, 'application/pdf')}
            response = requests.post(url, headers=headers, files=files, params=params)
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            raise Exception("Invalid API key")
        else:
            raise Exception(f"Error: {response.json().get('detail', 'Unknown error')}")
    
    def extract_with_patterns(self, pdf_path, include_ranges=False):
        """Extract using pattern matching (no auth required)."""
        url = f"{self.api_url}/convert"
        params = {"include_ranges": include_ranges}
        
        with open(pdf_path, 'rb') as f:
            files = {'file': f}
            response = requests.post(url, files=files, params=params)
        
        if response.status_code == 200:
            return response.text  # CSV content
        else:
            raise Exception(f"Error: {response.status_code}")

# Usage
extractor = BloodTestExtractor(
    api_url="https://your-app.railway.app",
    api_key="your-api-key"
)

# AI extraction (requires API key)
results = extractor.extract_with_ai("blood_test.pdf", include_ranges=True)
print(f"Found {results['marker_count']} markers")
for marker in results['results'][:5]:
    print(f"- {marker['marker']}: {marker['value']}")

# Pattern extraction (no API key needed)
csv_data = extractor.extract_with_patterns("blood_test.pdf")
with open("results.csv", "w") as f:
    f.write(csv_data)
```

### JavaScript/TypeScript

```typescript
import axios from 'axios';
import FormData from 'form-data';
import fs from 'fs';

class BloodTestExtractor {
  constructor(
    private apiUrl: string,
    private apiKey: string
  ) {}

  async extractWithAI(
    pdfPath: string, 
    includeRanges: boolean = false
  ): Promise<any> {
    const form = new FormData();
    form.append('file', fs.createReadStream(pdfPath));

    try {
      const response = await axios.post(
        `${this.apiUrl}/api/v1/ai-extract`,
        form,
        {
          params: { include_ranges: includeRanges },
          headers: {
            ...form.getHeaders(),
            'X-API-Key': this.apiKey
          }
        }
      );
      return response.data;
    } catch (error) {
      if (error.response?.status === 401) {
        throw new Error('Invalid API key');
      }
      throw error;
    }
  }

  async extractWithPatterns(
    pdfPath: string,
    includeRanges: boolean = false
  ): Promise<string> {
    const form = new FormData();
    form.append('file', fs.createReadStream(pdfPath));

    const response = await axios.post(
      `${this.apiUrl}/convert`,
      form,
      {
        params: { include_ranges: includeRanges },
        headers: form.getHeaders()
      }
    );
    return response.data;
  }
}

// Usage
const extractor = new BloodTestExtractor(
  'https://your-app.railway.app',
  'your-api-key'
);

// AI extraction
const results = await extractor.extractWithAI('blood_test.pdf', true);
console.log(`Found ${results.marker_count} markers`);
results.results.slice(0, 5).forEach(marker => {
  console.log(`- ${marker.marker}: ${marker.value}`);
});

// Pattern extraction
const csvData = await extractor.extractWithPatterns('blood_test.pdf');
fs.writeFileSync('results.csv', csvData);
```

### cURL Examples

**AI Extraction with Authentication:**
```bash
# Basic extraction
curl -X POST "https://your-app.railway.app/api/v1/ai-extract" \
  -H "X-API-Key: your-api-key" \
  -F "file=@blood_test.pdf"

# With reference ranges
curl -X POST "https://your-app.railway.app/api/v1/ai-extract?include_ranges=true" \
  -H "X-API-Key: your-api-key" \
  -F "file=@blood_test.pdf" \
  | jq '.'

# Save to file
curl -X POST "https://your-app.railway.app/api/v1/ai-extract" \
  -H "X-API-Key: your-api-key" \
  -F "file=@blood_test.pdf" \
  -o results.json
```

**Pattern Extraction (No Auth):**
```bash
# Basic extraction to CSV
curl -X POST "https://your-app.railway.app/convert" \
  -F "file=@blood_test.pdf" \
  -o results.csv

# Force specific format
curl -X POST "https://your-app.railway.app/convert?format=quest" \
  -F "file=@blood_test.pdf" \
  -o results.csv

# With reference ranges
curl -X POST "https://your-app.railway.app/convert?include_ranges=true" \
  -F "file=@blood_test.pdf" \
  -o results_with_ranges.csv
```

---

## Testing

### Local Testing

1. **Start the API server:**
```bash
python api.py
```

2. **Test with provided script:**
```bash
python test_ai_api.py pdf_reports/test.pdf your-test-api-key
```

3. **Test with curl:**
```bash
# Set your test API key in environment
export API_KEY="test-key-123"

# Test AI extraction
curl -X POST "http://localhost:8000/api/v1/ai-extract" \
  -H "X-API-Key: $API_KEY" \
  -F "file=@pdf_reports/ofer1.pdf"
```

### Production Testing

Replace `localhost:8000` with your Railway URL:
```bash
curl -X POST "https://your-app.railway.app/api/v1/ai-extract" \
  -H "X-API-Key: your-production-key" \
  -F "file=@test.pdf"
```

---

## Deployment on Railway

### Step 1: Prepare Repository

Ensure your repository has:
- `api.py` - Main API application
- `requirements.txt` - Python dependencies
- `Procfile` - Railway deployment config
- `.env.example` - Environment variable template

### Step 2: Configure Railway

1. **Create new project** in Railway
2. **Connect GitHub repository**
3. **Add environment variables:**
   ```
   API_SECRET_KEY=generate-a-secure-random-key
   ANTHROPIC_API_KEY=sk-ant-your-claude-api-key
   PORT=8000
   ```

### Step 3: Deploy

Railway will automatically:
1. Detect Python application
2. Install dependencies from `requirements.txt`
3. Use `Procfile` to start the server
4. Provide a public URL

### Step 4: Verify Deployment

Test the health endpoint:
```bash
curl https://your-app.railway.app/
```

---

## Rate Limiting & Best Practices

### Recommendations

1. **File Size**: Limit PDFs to under 10MB for optimal performance
2. **Concurrent Requests**: Process one file at a time to avoid overloading
3. **Caching**: Consider caching results for identical PDFs
4. **Error Handling**: Implement retry logic with exponential backoff
5. **Monitoring**: Log all API calls for usage tracking

### Example Rate Limiting (Client-Side)

```python
import time
from typing import List
import hashlib

class RateLimitedExtractor:
    def __init__(self, api_url, api_key, max_requests_per_minute=10):
        self.api_url = api_url
        self.api_key = api_key
        self.max_rpm = max_requests_per_minute
        self.request_times = []
        self.cache = {}
    
    def _wait_if_needed(self):
        """Implement rate limiting."""
        now = time.time()
        # Remove requests older than 1 minute
        self.request_times = [t for t in self.request_times if now - t < 60]
        
        if len(self.request_times) >= self.max_rpm:
            # Wait until the oldest request is > 1 minute old
            sleep_time = 60 - (now - self.request_times[0]) + 1
            time.sleep(sleep_time)
        
        self.request_times.append(now)
    
    def _get_file_hash(self, pdf_path):
        """Generate hash for caching."""
        with open(pdf_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    
    def extract(self, pdf_path, use_cache=True):
        """Extract with rate limiting and caching."""
        # Check cache
        if use_cache:
            file_hash = self._get_file_hash(pdf_path)
            if file_hash in self.cache:
                print("Using cached result")
                return self.cache[file_hash]
        
        # Rate limit
        self._wait_if_needed()
        
        # Make request
        url = f"{self.api_url}/api/v1/ai-extract"
        headers = {"X-API-Key": self.api_key}
        
        with open(pdf_path, 'rb') as f:
            files = {'file': f}
            response = requests.post(url, headers=headers, files=files)
        
        if response.status_code == 200:
            result = response.json()
            if use_cache:
                self.cache[file_hash] = result
            return result
        else:
            raise Exception(f"API Error: {response.status_code}")
```

---

## Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| 401 Unauthorized | Invalid API key | Check X-API-Key header matches API_SECRET_KEY |
| 500 Server Error | Missing ANTHROPIC_API_KEY | Set Claude API key in environment |
| No data extracted | Unsupported PDF format | Try pattern-based endpoint or check PDF quality |
| Timeout errors | Large PDF file | Reduce file size or increase timeout |
| Connection refused | Server not running | Check deployment logs in Railway |

### Debug Checklist

1. **Environment Variables Set?**
   ```bash
   # Check locally
   echo $API_SECRET_KEY
   echo $ANTHROPIC_API_KEY
   
   # Check in Railway dashboard
   Railway > Variables > Check all are set
   ```

2. **API Running?**
   ```bash
   curl https://your-app.railway.app/
   ```

3. **Authentication Working?**
   ```bash
   # Should return 401
   curl -X POST https://your-app.railway.app/api/v1/ai-extract \
     -H "X-API-Key: wrong-key" \
     -F "file=@test.pdf"
   ```

4. **Check Logs:**
   - Railway: Dashboard > Deployments > View Logs
   - Local: Check terminal output

---

## Security Considerations

1. **API Key Storage**
   - Never commit API keys to git
   - Use environment variables
   - Rotate keys periodically
   - Use different keys for dev/staging/production

2. **HTTPS Only**
   - Railway provides HTTPS by default
   - Never send API keys over HTTP

3. **Input Validation**
   - PDFs are validated before processing
   - File size limits prevent abuse
   - Non-PDF files are rejected

4. **Error Messages**
   - Generic error messages to users
   - Detailed errors only in server logs
   - Never expose internal paths or keys

---

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review Railway deployment logs
3. Test with the provided test script
4. Verify environment variables are set correctly