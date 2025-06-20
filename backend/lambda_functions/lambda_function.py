import json
import os
import urllib.request
import urllib.parse
import boto3
import re
from datetime import datetime

# Initialize AWS clients for PARIS REGION
textract = boto3.client('textract', region_name='eu-west-3')
s3 = boto3.client('s3', region_name='eu-west-3')

# Updated bucket name for Paris
BUCKET_NAME = 'shelfsaver-images-paris'

# JSON Configuration for regex patterns
REGEX_CONFIG = {
    "parsing": {
        "regex_patterns": {
            "expiry_date": [
                r"(?i)(exp|expir|use by|best before|à consommer avant)[^\d]*([0-9]{1,2}[/\-\.][0-9]{1,2}[/\-\.][0-9]{2,4})",
                r"([0-9]{1,2}[/\-\.][0-9]{1,2}[/\-\.][0-9]{2,4})"
            ],
            "product_name": [
                r"^([A-Z][A-Za-z\s]+)$",
                r"([A-Z][A-Za-z\s]{3,30})"
            ],
            "quantity": [
                r"(\d+)\s*(g|kg|ml|l|pcs|pieces)",
                r"quantity[:\s]*(\d+)"
            ],
            "barcode": [
                r"(\d{13})",
                r"(\d{8})"
            ]
        }
    },
    "confidence_weights": {
        "expiry_date": 40,
        "product_name": 30,
        "quantity": 20,
        "barcode": 10
    }
}

def lambda_handler(event, context):
    try:
        print("🚀 ShelfSaver webhook received in PARIS! 🇫🇷")
        
        bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        if not bot_token:
            return {'statusCode': 500, 'body': 'Bot token not configured'}

        body = json.loads(event.get('body', '{}'))
        message = body.get('message', {})
        chat_id = message.get('chat', {}).get('id')
        text = message.get('text', '')

        if chat_id:
            if 'photo' in message:
                photo = message['photo'][-1]
                file_id = photo['file_id']
                
                print(f"📸 Processing photo in Paris region")
                
                # Process with Paris infrastructure
                result = process_product_paris(bot_token, file_id, chat_id)
                
                if result:
                    send_structured_product_result(bot_token, chat_id, result)
                else:
                    send_message(bot_token, chat_id, "❌ Could not process image. Try again with better lighting!")
            
            elif text:
                if text.lower() in ['/start', 'start']:
                    welcome_text = "👋 Welcome to ShelfSaver Pro! 🇫🇷\n\n📸 Send product photos for AI-powered expiry tracking\n🔬 Enterprise-grade OCR processing\n📊 Professional data extraction\n\n🗼 Powered by AWS Paris Region!"
                    send_message(bot_token, chat_id, welcome_text)
                elif text.lower() == '/debug':
                    debug_info = f"🔧 Debug Info:\n📍 Region: Europe (Paris) eu-west-3\n🪣 Bucket: {BUCKET_NAME}\n🤖 OCR: AWS Textract"
                    send_message(bot_token, chat_id, debug_info)
                else:
                    send_message(bot_token, chat_id, "📸 Send a product photo for analysis!")
    
    except Exception as e:
        print(f"💥 Error: {e}")
        import traceback
        print("Traceback:", traceback.format_exc())
        return {'statusCode': 500, 'body': f'Error: {str(e)}'}
    
    return {'statusCode': 200, 'body': json.dumps({'status': 'ok', 'region': 'eu-west-3'})}

def process_product_paris(bot_token, file_id, chat_id):
    """Process product with Paris region infrastructure"""
    try:
        send_message(bot_token, chat_id, "🔬 AI Analysis Starting... 🇫🇷\n📸 Image → 📝 Textract Paris → 🧠 Pattern Match")
        
        # Step 1: Download and store in Paris S3
        image_s3_key = store_telegram_image_paris(bot_token, file_id)
        if not image_s3_key:
            return None
        
        # Step 2: Extract text with Paris Textract
        raw_text = extract_text_textract_paris(image_s3_key)
        if not raw_text:
            return None
            
        # Step 3: Store raw text in Paris S3
        text_s3_key = store_raw_text_paris(file_id, raw_text)
        
        # Step 4: Apply regex patterns
        structured_data = apply_json_regex_patterns(raw_text)
        
        # Step 5: Build result
        result = {
            'file_id': file_id,
            'image_s3_key': image_s3_key,
            'text_s3_key': text_s3_key,
            'raw_text': raw_text[:300],
            'region': 'eu-west-3',
            'ocr_provider': 'AWS Textract Paris',
            **structured_data
        }
        
        print(f"✅ Paris processing complete: {json.dumps(result, indent=2)}")
        return result
        
    except Exception as e:
        print(f"💥 Error in Paris processing: {e}")
        return None

def store_telegram_image_paris(bot_token, file_id):
    """Download from Telegram and store in Paris S3"""
    try:
        print(f"📥 Downloading to Paris S3: {BUCKET_NAME}")
        
        # Get file info
        file_info_url = f"https://api.telegram.org/bot{bot_token}/getFile?file_id={file_id}"
        req = urllib.request.Request(file_info_url)
        response = urllib.request.urlopen(req)
        file_data = json.loads(response.read().decode())
        
        if not file_data.get('ok'):
            return None
            
        file_path = file_data['result']['file_path']
        
        # Download image
        image_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
        req = urllib.request.Request(image_url)
        response = urllib.request.urlopen(req)
        image_data = response.read()
        
        print(f"📥 Downloaded {len(image_data)} bytes")
        
        # Store in Paris S3
        s3_key = f"images/{file_id}.jpg"
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=s3_key,
            Body=image_data,
            ContentType='image/jpeg'
        )
        
        print(f"✅ Stored in Paris S3: {BUCKET_NAME}/{s3_key}")
        return s3_key
        
    except Exception as e:
        print(f"💥 Error storing in Paris: {e}")
        return None

def extract_text_textract_paris(s3_key):
    """Extract text using AWS Textract in Paris"""
    try:
        print(f"🔍 Running Textract in Paris on {BUCKET_NAME}/{s3_key}")
        
        response = textract.detect_document_text(
            Document={
                'S3Object': {
                    'Bucket': BUCKET_NAME,
                    'Name': s3_key
                }
            }
        )
        
        print(f"✅ Textract Paris success! Found {len(response['Blocks'])} blocks")
        
        # Extract text
        text_lines = []
        for block in response['Blocks']:
            if block['BlockType'] == 'LINE':
                text_lines.append(block['Text'])
                print(f"📝 Line: '{block['Text']}'")
        
        raw_text = '\n'.join(text_lines)
        print(f"✅ Extracted {len(raw_text)} characters")
        
        if not raw_text.strip():
            print("⚠️ No text extracted - image might be unclear")
            return None
            
        return raw_text
        
    except Exception as e:
        print(f"💥 Textract Paris error: {e}")
        import traceback
        print(f"💥 Traceback: {traceback.format_exc()}")
        return None

def store_raw_text_paris(file_id, text):
    """Store raw OCR text in Paris S3"""
    try:
        text_s3_key = f"text/{file_id}.txt"
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=text_s3_key,
            Body=text.encode('utf-8'),
            ContentType='text/plain'
        )
        print(f"✅ Text stored in Paris: {text_s3_key}")
        return text_s3_key
    except Exception as e:
        print(f"Error storing text in Paris: {e}")
        return f"text/{file_id}.txt"

def apply_json_regex_patterns(text):
    """Apply JSON regex patterns to extract structured data"""
    try:
        config = REGEX_CONFIG
        patterns = config['parsing']['regex_patterns']
        weights = config['confidence_weights']
        
        result = {
            'product_name': None,
            'expiry_date': None,
            'quantity': None,
            'barcode': None,
            'confidence': 0,
            'extraction_details': {}
        }
        
        # Apply patterns
        for category, pattern_list in patterns.items():
            for pattern in pattern_list:
                matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
                if matches:
                    result['extraction_details'][category] = {
                        'pattern': pattern,
                        'matches': matches[:3]
                    }
                    
                    if category == 'expiry_date' and not result['expiry_date']:
                        result['expiry_date'] = clean_date(matches[0])
                    elif category == 'product_name' and not result['product_name']:
                        result['product_name'] = clean_product_name(matches[0])
                    elif category == 'quantity' and not result['quantity']:
                        result['quantity'] = clean_quantity(matches[0])
                    elif category == 'barcode' and not result['barcode']:
                        result['barcode'] = matches[0] if isinstance(matches[0], str) else matches[0][0]
                    
                    break
        
        # Calculate confidence
        confidence = 0
        for category, weight in weights.items():
            if result[category]:
                confidence += weight
        
        result['confidence'] = confidence
        
        # Fallback for product name
        if not result['product_name']:
            lines = text.split('\n')
            for line in lines[:5]:
                if len(line.strip()) > 5:
                    result['product_name'] = line.strip()[:40]
                    break
        
        if not result['product_name']:
            result['product_name'] = "Unknown Product"
            
        return result
        
    except Exception as e:
        print(f"Error applying patterns: {e}")
        return {
            'product_name': 'Processing Error',
            'expiry_date': None,
            'quantity': None,
            'barcode': None,
            'confidence': 20,
            'extraction_details': {'error': str(e)}
        }

def clean_date(date_match):
    if isinstance(date_match, tuple):
        date_str = date_match[1] if len(date_match) > 1 else date_match[0]
    else:
        date_str = str(date_match)
    
    date_str = re.sub(r'[^\d/\-\.]', '', date_str)
    return date_str if date_str else None

def clean_product_name(name_match):
    if isinstance(name_match, tuple):
        name = name_match[0]
    else:
        name = str(name_match)
    
    return name.strip()[:50]

def clean_quantity(qty_match):
    if isinstance(qty_match, tuple):
        return qty_match[0]
    return str(qty_match)

def send_structured_product_result(bot_token, chat_id, result):
    """Send professional analysis result with error handling"""
    try:
        name = result['product_name']
        expiry = result['expiry_date'] or 'Not detected'
        confidence = result['confidence']
        
        # Simple text without markdown to avoid parsing errors
        text = f"🔬 AI Analysis Complete 🇫🇷\n\n"
        text += f"📦 Product: {name}\n"
        text += f"📅 Expiry: {expiry}\n"
        text += f"📊 Confidence: {confidence}%\n"
        
        if result.get('quantity'):
            text += f"⚖️ Quantity: {result['quantity']}\n"
        
        if result.get('barcode'):
            text += f"🏷️ Barcode: {result['barcode']}\n"
        
        text += f"\n🎯 OCR: {result.get('ocr_provider', 'AWS Textract')}"
        text += f"\n📍 Region: Paris (eu-west-3)"
        
        # Try simple message first
        send_message(bot_token, chat_id, text)
        print("✅ Simple message sent successfully")
        
        # Then try to send buttons separately
        try:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            button_data = {
                'chat_id': chat_id,
                'text': "Choose an action:",
                'reply_markup': {
                    'inline_keyboard': [
                        [
                            {'text': '✅ Accept', 'callback_data': f'accept_{result["file_id"][:20]}'},
                            {'text': '✏️ Edit', 'callback_data': f'edit_{result["file_id"][:20]}'}
                        ]
                    ]
                }
            }
            
            req = urllib.request.Request(url, 
                                        data=json.dumps(button_data).encode(),
                                        headers={'Content-Type': 'application/json'},
                                        method='POST')
            urllib.request.urlopen(req)
            print("✅ Buttons sent successfully")
            
        except Exception as e:
            print(f"⚠️ Buttons failed but main message worked: {e}")
        
    except Exception as e:
        print(f"💥 Error sending result: {e}")
        # Fallback to simple message
        try:
            simple_text = f"✅ Analysis complete!\nProduct: {result.get('product_name', 'Unknown')}\nExpiry: {result.get('expiry_date', 'Not found')}"
            send_message(bot_token, chat_id, simple_text)
        except:
            print("💥 Even simple message failed")

def send_message(bot_token, chat_id, text):
    """Send simple message"""
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = urllib.parse.urlencode({
            'chat_id': chat_id,
            'text': text
        }).encode()
        req = urllib.request.Request(url, data=data, method='POST')
        urllib.request.urlopen(req)
    except Exception as e:
        print(f"Error sending message: {e}")