# cURL Commands for LoadBoard Endpoints

## POST /loadboard/post_loads

### Windows PowerShell (using Invoke-RestMethod)

```powershell
$body = @{
    xml = "<LBNLoadPostings><PostingAccount><UserName>testuser</UserName><UserID>12345</UserID></PostingAccount><PostLoads><load><tracking-number>TRACK001</tracking-number><origin><city>New York</city><state>NY</state></origin><destination><city>Los Angeles</city><state>CA</state></destination></load></PostLoads></LBNLoadPostings>"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://127.0.0.1:8000/loadboard/post_loads" -Method POST -ContentType "application/json" -Body $body
```

### Windows PowerShell (one-liner)

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/loadboard/post_loads" -Method POST -ContentType "application/json" -Body '{"xml":"<LBNLoadPostings><PostingAccount><UserName>testuser</UserName><UserID>12345</UserID></PostingAccount><PostLoads><load><tracking-number>TRACK001</tracking-number><origin><city>New York</city><state>NY</state></origin><destination><city>Los Angeles</city><state>CA</state></destination></load></PostLoads></LBNLoadPostings>"}'
```

### Linux/Mac/Git Bash (standard curl)

```bash
curl -X POST "http://127.0.0.1:8000/loadboard/post_loads" \
  -H "Content-Type: application/json" \
  -d '{
    "xml": "<LBNLoadPostings><PostingAccount><UserName>testuser</UserName><UserID>12345</UserID></PostingAccount><PostLoads><load><tracking-number>TRACK001</tracking-number><origin><city>New York</city><state>NY</state></origin><destination><city>Los Angeles</city><state>CA</state></destination></load></PostLoads></LBNLoadPostings>"
  }'
```

### Full XML Example (with all fields)

```bash
curl -X POST "http://127.0.0.1:8000/loadboard/post_loads" \
  -H "Content-Type: application/json" \
  -d '{
    "xml": "<LBNLoadPostings><PostingAccount><UserName>testuser</UserName><Password>testpass</Password><ContactName>John Doe</ContactName><ContactPhone>555-1234</ContactPhone><ContactEmail>john@example.com</ContactEmail><CompanyName>Test Trucking Co</CompanyName><UserID>12345</UserID><mcNumber>MC123456</mcNumber><dotNumber>DOT123456</dotNumber></PostingAccount><PostLoads><load><tracking-number>TRACK001</tracking-number><origin><city>New York</city><state>NY</state><postcode>10001</postcode><latitude>40.7128</latitude><longitude>-74.0060</longitude><date-start><year>2024</year><month>1</month><day>15</day><hour>8</hour><minute>0</minute></date-start></origin><destination><city>Los Angeles</city><state>CA</state><postcode>90001</postcode><latitude>34.0522</latitude><longitude>-118.2437</longitude><date-start><year>2024</year><month>1</month><day>18</day><hour>10</hour><minute>0</minute></date-start></destination><equipment><dryvan/></equipment><loadsize fullload=\"true\"><length>53</length><width>102</width><height>110</height><weight>45000</weight></loadsize><load-count>1</load-count><stops>0</stops><distance>2790</distance><rate>2500.00</rate><comment>Fragile cargo - handle with care</comment></load></PostLoads></LBNLoadPostings>"
  }'
```

## POST /loadboard/remove_loads

### Windows PowerShell

```powershell
$body = @{
    xml = "<LBNLoadPostings><PostingAccount><UserName>testuser</UserName><UserID>12345</UserID></PostingAccount><RemoveLoads><load><tracking-number>TRACK001</tracking-number></load></RemoveLoads></LBNLoadPostings>"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://127.0.0.1:8000/loadboard/remove_loads" -Method POST -ContentType "application/json" -Body $body
```

### Linux/Mac/Git Bash

```bash
curl -X POST "http://127.0.0.1:8000/loadboard/remove_loads" \
  -H "Content-Type: application/json" \
  -d '{
    "xml": "<LBNLoadPostings><PostingAccount><UserName>testuser</UserName><UserID>12345</UserID></PostingAccount><RemoveLoads><load><tracking-number>TRACK001</tracking-number></load></RemoveLoads></LBNLoadPostings>"
  }'
```

## Using curl.exe on Windows (if installed)

If you have curl.exe installed on Windows, you can use:

```cmd
curl.exe -X POST "http://127.0.0.1:8000/loadboard/post_loads" -H "Content-Type: application/json" -d "{\"xml\":\"<LBNLoadPostings><PostingAccount><UserName>testuser</UserName><UserID>12345</UserID></PostingAccount><PostLoads><load><tracking-number>TRACK001</tracking-number><origin><city>New York</city><state>NY</state></origin><destination><city>Los Angeles</city><state>CA</state></destination></load></PostLoads></LBNLoadPostings>\"}"
```

## Notes

- Replace `127.0.0.1:8000` with your actual server URL if different
- Make sure Supabase is configured (SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY) for the endpoints to work
- The XML content should be properly escaped in JSON (quotes escaped as `\"`)
- For PowerShell, using `Invoke-RestMethod` is recommended over curl alias

