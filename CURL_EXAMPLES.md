# LoadBoard Network API - cURL Examples

## Option 1: Send Raw XML (Recommended)

This is the simplest approach - send the XML directly with `Content-Type: application/xml`:

```bash
curl -X POST 'https://route-optimization-six.vercel.app/loadboard/post_loads' \
  -H 'Content-Type: application/xml' \
  -d '<LBNLoadPostings>
 <PostingAccount>
 <UserName></UserName>
 <Password></Password>
 <ContactName></ContactName>
 <ContactPhone></ContactPhone>
 <ContactFax/>
 <ContactEmail></ContactEmail>
 <CompanyName></CompanyName>
 <UserID></UserID>
 <mcNumber></mcNumber>
 <dotNumber></dotNumber>
 </PostingAccount>
 <PostLoads>
 <load>
<tracking-number>0000000000</tracking-number>
 <origin>
 <city>BAY CITY</city>
 <state>TX</state>
 <postcode/>
 <county/>
 <country/>
 <latitude>0</latitude>
 <longitude>0</longitude>
 <date-start>
 <year>2022</year>
 <month>11</month>
 <day>28</day>
 <hour>7</hour>
 <minute>00</minute>
 </date-start>
 <date-end>
 <year/>
 <month/>
 <day/>
 <hour/>
 <minute/>
 </date-end>
</origin>
 <destination>
 <city>PENSACOLA</city>
 <state>FL</state>
 <postcode/>
 <county/>
 <country/>
 <latitude>0</latitude>
 <longitude>0</longitude>
 <date-start>
 <year>2022</year>
 <month>11</month>
 <day>29</day>
 <hour>7</hour>
 <minute>59</minute>
 </date-start>
 <date-end>
 <year/>
 <month/>
 <day/>
 <hour/>
 <minute/>
 </date-end>
 </destination>
 <equipment>
 <t/>
 </equipment>
 <loadsize fullload="true">
 <length/>
 <width/>
 <height/>
 <weight>45</weight>
 </loadsize>
 <load-count>1</load-count>
 <stops>3</stops>
 <distance>600</distance>
 <rate>0</rate>
 <comment></comment>
 </load>
 </PostLoads>
</LBNLoadPostings>'
```

## Option 2: Send JSON with Escaped XML

If you need to send JSON, you must escape newlines as `\n`:

```bash
curl -X POST 'https://route-optimization-six.vercel.app/loadboard/post_loads' \
  -H 'Content-Type: application/json' \
  -d '{
  "xml": "<LBNLoadPostings>\n <PostingAccount>\n <UserName></UserName>\n <Password></Password>\n <ContactName></ContactName>\n <ContactPhone></ContactPhone>\n <ContactFax/>\n <ContactEmail></ContactEmail>\n <CompanyName></CompanyName>\n <UserID></UserID>\n <mcNumber></mcNumber>\n <dotNumber></dotNumber>\n </PostingAccount>\n <PostLoads>\n <load>\n<tracking-number>0000000000</tracking-number>\n <origin>\n <city>BAY CITY</city>\n <state>TX</state>\n <postcode/>\n <county/>\n <country/>\n <latitude>0</latitude>\n <longitude>0</longitude>\n <date-start>\n <year>2022</year>\n <month>11</month>\n <day>28</day>\n <hour>7</hour>\n <minute>00</minute>\n </date-start>\n <date-end>\n <year/>\n <month/>\n <day/>\n <hour/>\n <minute/>\n </date-end>\n</origin>\n <destination>\n <city>PENSACOLA</city>\n <state>FL</state>\n <postcode/>\n <county/>\n <country/>\n <latitude>0</latitude>\n <longitude>0</longitude>\n <date-start>\n <year>2022</year>\n <month>11</month>\n <day>29</day>\n <hour>7</hour>\n <minute>59</minute>\n </date-start>\n <date-end>\n <year/>\n <month/>\n <day/>\n <hour/>\n <minute/>\n </date-end>\n </destination>\n <equipment>\n <t/>\n </equipment>\n <loadsize fullload=\"true\">\n <length/>\n <width/>\n <height/>\n <weight>45</weight>\n </loadsize>\n <load-count>1</load-count>\n <stops>3</stops>\n <distance>600</distance>\n <rate>0</rate>\n <comment></comment>\n </load>\n </PostLoads>\n</LBNLoadPostings>"
}'
```

## Option 3: Use a File for Raw XML

Save your XML to a file and send it:

```bash
# Save XML to file.xml
curl -X POST 'https://route-optimization-six.vercel.app/loadboard/post_loads' \
  -H 'Content-Type: application/xml' \
  --data-binary @file.xml
```

## Option 4: Use a File for JSON

Save your JSON (with escaped XML) to a file and send it:

```bash
# Save JSON to request.json
curl -X POST 'https://route-optimization-six.vercel.app/loadboard/post_loads' \
  -H 'Content-Type: application/json' \
  -d @request.json
```

## PowerShell Example (Raw XML)

For Windows PowerShell:

```powershell
$xml = @"
<LBNLoadPostings>
 <PostingAccount>
 <UserName></UserName>
 <Password></Password>
 </PostingAccount>
 <PostLoads>
 <load>
<tracking-number>0000000000</tracking-number>
 </load>
 </PostLoads>
</LBNLoadPostings>
"@

Invoke-RestMethod -Uri "https://route-optimization-six.vercel.app/loadboard/post_loads" `
  -Method POST `
  -ContentType "application/xml" `
  -Body $xml
```

## Notes

- **Raw XML is recommended** - It's simpler and doesn't require escaping
- **JSON requires escaping** - All newlines must be `\n`, quotes must be `\"`
- The endpoint accepts both formats automatically based on `Content-Type` header
- For LoadBoard Network compatibility, use `Content-Type: application/xml`

