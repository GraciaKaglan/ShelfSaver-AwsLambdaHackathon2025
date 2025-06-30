import os
import re
import json
import uuid
import boto3
import urllib.parse
import urllib.request
from decimal import Decimal
from datetime import datetime, timedelta, date

# Initialize AWS clients for PARIS REGION
textract = boto3.client('textract', region_name='eu-west-3')
s3 = boto3.client('s3', region_name='eu-west-3')

#DB
dynamodb = boto3.resource('dynamodb', region_name='eu-north-1')
table = dynamodb.Table('shelf-saver-products')

# Updated bucket name for Paris
BUCKET_NAME = 'shelfsaver-images-paris'

# Helper to convert DynamoDB Decimal to regular numbers
class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super(DecimalEncoder, self).default(o)


# JSON Configuration for regex patterns
REGEX_CONFIG = {
    "parsing": {
        "regex_patterns": {
            "expiry_date": [
                r"DLC : (..?/..?/..)",
                r"([0-9]{1,2}[/\-\.][0-9]{1,2}[/\-\.][0-9]{2,4})"
            ],
            "product_name": [
                r"([A-Z ]{5,})",
                r"([A-Z][A-Za-z\s]{3,30})"
            ],
            "quantity": [
                r"x|X([0-9])"
            ],
            "barcode": [
                r"(\(01\)[0-9]+\(17\)[0-9]+\(10\)[0-9]+)",
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
    print(f"🔍 DEBUG - Full event: {json.dumps(event, indent=2)}")

    # CORS headers for API requests
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type',
        'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS'
    }
    
    # Check for HTTP API v2.0 format (API Gateway)
    if event.get('version') == '2.0' and 'routeKey' in event:
        # This is HTTP API v2.0 (API Gateway)
        method = event['requestContext']['http']['method']
        route_key = event['routeKey']
        raw_path = event.get('rawPath', '')
        
        print(f"🌐 HTTP API v2.0 detected - Method: {method}, RouteKey: {route_key}, RawPath: {raw_path}")
        
        # Handle CORS preflight
        if method == 'OPTIONS':
            return {
                'statusCode': 200,
                'headers': headers,
                'body': ''
            }
        
        return handle_http_api_v2_request(event, context, headers, method, route_key, raw_path)
    
    # Check if this is a traditional REST API request (has httpMethod)
    elif 'httpMethod' in event:
        # This is traditional REST API
        method = event['httpMethod']
        path = event.get('path', '')
        
        print(f"🌐 REST API Request: {method} {path}")
        return handle_api_gateway_request(event, context, headers, method, path)
    
    # Check if this is a Lambda Function URL request (has requestContext.http but no version)
    elif 'requestContext' in event and 'http' in event['requestContext'] and not event.get('version'):
        # This is a Lambda Function URL request
        method = event['requestContext']['http']['method']
        path = event['requestContext']['http']['path']
        
        print(f"🌐 Lambda URL Request: {method} {path}")
        return handle_api_request_lambda_url(event, context, headers, method, path)
    
    # Otherwise, treat as Telegram webhook
    else:
        print("📱 Telegram Webhook Request")
        return handle_telegram_webhook(event, context)

def handle_http_api_v2_request(event, context, headers, method, route_key, raw_path):
    """Handle HTTP API v2.0 requests (API Gateway)"""
    try:
        print(f"🌐 Processing HTTP API v2.0 Request:")
        print(f"   Method: {method}")
        print(f"   RouteKey: {route_key}")
        print(f"   RawPath: {raw_path}")
        
        # Extract path parameters
        path_params = event.get('pathParameters') or {}
        print(f"   Path Parameters: {path_params}")
        
        # Use routeKey for matching (this is the most reliable for HTTP API v2.0)
        if method == 'GET' and route_key == 'GET /products':
            print("✅ Matched: GET /products")
            return get_all_products(event, headers)
        elif method == 'GET' and route_key == 'GET /products/{id}':
            print("✅ Matched: GET /products/{id}")
            product_id = path_params.get('id')
            print(f"   Product ID: {product_id}")
            return get_product(product_id, headers)
        elif method == 'PUT' and route_key == 'PUT /products/{id}':
            print("✅ Matched: PUT /products/{id}")
            product_id = path_params.get('id')
            return update_product(product_id, event, headers)
        elif method == 'POST' and route_key == 'POST /webhook':
            print("✅ Matched: POST /webhook")
            return handle_telegram_webhook(event, context)
        else:
            print(f"❌ No match found for: {method} {route_key}")
            return {
                'statusCode': 404,
                'headers': headers,
                'body': json.dumps({
                    'error': f'API endpoint not found',
                    'method': method,
                    'route_key': route_key,
                    'raw_path': raw_path,
                    'path_params': path_params,
                    'available_endpoints': [
                        'GET /products',
                        'GET /products/{id}',
                        'PUT /products/{id}',
                        'POST /webhook'
                    ]
                })
            }
            
    except Exception as e:
        print(f"💥 HTTP API v2.0 Error: {e}")
        import traceback
        print(f"💥 Traceback: {traceback.format_exc()}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': str(e)})
        }
        
def handle_api_request_lambda_url(event, context, headers, method, path):
    """Handle API requests from Lambda Function URL (backup)"""
    try:
        print(f"🌐 Processing Lambda URL Request: {method} {path}")
        
        if method == 'GET' and path == '/products':
            return get_all_products(event, headers)
        elif method == 'GET' and path.startswith('/products/'):
            product_id = path.split('/')[-1]
            return get_product(product_id, headers)
        elif method == 'PUT' and path.startswith('/products/'):
            product_id = path.split('/')[-1]
            return update_product(product_id, event, headers)
        else:
            return {
                'statusCode': 404,
                'headers': headers,
                'body': json.dumps({'error': f'API endpoint not found: {method} {path}'})
            }
            
    except Exception as e:
        print(f"💥 Lambda URL Error: {e}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': str(e)})
        }

def handle_api_request(event, context, headers):
    """Handle API requests from frontend"""
    try:
        method = event['httpMethod']
        path = event.get('path', '')
        
        print(f"🌐 API Request: {method} {path}")
        
        if method == 'GET' and path == '/products':
            return get_all_products(event, headers)
        elif method == 'GET' and path.startswith('/products/'):
            product_id = path.split('/')[-1]
            return get_product(product_id, headers)
        elif method == 'PUT' and path.startswith('/products/'):
            product_id = path.split('/')[-1]
            return update_product(product_id, event, headers)
        else:
            return {
                'statusCode': 404,
                'headers': headers,
                'body': json.dumps({'error': 'API endpoint not found'})
            }
            
    except Exception as e:
        print(f"💥 API Error: {e}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': str(e)})
        }

def get_all_products(event, headers):
    """Get all products for a user"""
    try:
        # Get user_id from query parameters (handle both API Gateway and Lambda Function URL formats)
        query_params = event.get('queryStringParameters') or {}
        
        # For Lambda Function URLs, parse rawQueryString if queryStringParameters is None
        if not query_params and event.get('rawQueryString'):
            import urllib.parse
            query_params = dict(urllib.parse.parse_qsl(event['rawQueryString']))
        
        user_id = query_params.get('user_id')
        
        print(f"📊 Fetching products for user: {user_id}")
        
        if user_id and user_id != 'demo':
            # Filter by user_id
            response = table.scan(
                FilterExpression=boto3.dynamodb.conditions.Attr('user_id').eq(user_id)
            )
        else:
            # Get all products (for demo)
            response = table.scan()
        
        products = response['Items']
        
        # Add S3 image URLs
        for product in products:
            if product.get('image_s3_key'):
                product['image_url'] = f"https://{BUCKET_NAME}.s3.eu-west-3.amazonaws.com/{product['image_s3_key']}"
        
        print(f"✅ Found {len(products)} products")
        
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'products': products,
                'count': len(products)
            }, cls=DecimalEncoder)
        }
        
    except Exception as e:
        print(f"💥 Get products error: {e}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': str(e)})
        }

def get_product(product_id, headers):
    """Get a single product"""
    try:
        print(f"🔍 Fetching product: {product_id}")
        
        response = table.get_item(Key={'product_id': product_id})
        
        if 'Item' in response:
            product = response['Item']
            # Add S3 image URL
            if product.get('image_s3_key'):
                product['image_url'] = f"https://{BUCKET_NAME}.s3.eu-west-3.amazonaws.com/{product['image_s3_key']}"
            
            return {
                'statusCode': 200,
                'headers': headers,
                'body': json.dumps(product, cls=DecimalEncoder)
            }
        else:
            return {
                'statusCode': 404,
                'headers': headers,
                'body': json.dumps({'error': 'Product not found'})
            }
            
    except Exception as e:
        print(f"💥 Get product error: {e}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': str(e)})
        }

def update_product(product_id, event, headers):
    """Update a product"""
    try:
        # Parse request body
        body = json.loads(event['body'])
        
        print(f"✏️ Updating product {product_id}: {body}")
        
        # Update product
        update_expression = []
        expression_values = {}
        expression_names = {}
        
        for key, value in body.items():
            if key != 'product_id':
                if key == 'status':
                    # Handle reserved keyword 'status'
                    update_expression.append(f"#status = :status")
                    expression_values[':status'] = value
                    expression_names['#status'] = 'status'
                else:
                    update_expression.append(f"{key} = :{key}")
                    expression_values[f":{key}"] = value

        if update_expression:
            update_params = {
                'Key': {'product_id': product_id},
                'UpdateExpression': 'SET ' + ', '.join(update_expression),
                'ExpressionAttributeValues': expression_values
            }
            
            # Add ExpressionAttributeNames only if we have reserved keywords
            if expression_names:
                update_params['ExpressionAttributeNames'] = expression_names
            
            table.update_item(**update_params)
        
        print(f"✅ Product {product_id} updated successfully")
        
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({'message': 'Product updated successfully'})
        }
        
    except Exception as e:
        print(f"💥 Update product error: {e}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': str(e)})
        }

def handle_telegram_webhook(event, context):
    """Handle Telegram webhook (your existing code)"""
    try:
        print("🚀 ShelfSaver webhook received in PARIS! 🇫🇷")
        
        bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        if not bot_token:
            return {'statusCode': 500, 'body': 'Bot token not configured'}

        body = json.loads(event.get('body', '{}'))
        
        # 🔔 ADD NOTIFICATION HANDLING HERE
        if body.get('notification_test'):
            print("🔔 Notification test triggered via webhook")
            user_id = body.get('user_id', 'demo')
            
            try:
                # Get REAL expiring products from database
                response = table.scan(
                    FilterExpression=boto3.dynamodb.conditions.Attr('user_id').eq(str(user_id))
                )
                
                products = response['Items']
                expiring_products = []
                
                # Check which products are actually expiring
                today = date.today()
                
                for product in products:
                    expiry_str = product.get('expiry_date', '')
                    if expiry_str and expiry_str != 'Unknown':
                        try:
                            # Parse DD/MM/YY format
                            parts = expiry_str.split('/')
                            if len(parts) == 3:
                                day = int(parts[0])
                                month = int(parts[1])
                                year = int(parts[2])
                                
                                # Convert 2-digit year to 4-digit
                                if year < 100:
                                    year += 2000 if year < 50 else 1900
                                
                                expiry_date = date(year, month, day)
                                days_until_expiry = (expiry_date - today).days
                                
                                # Include products expiring in next 3 days
                                if 0 <= days_until_expiry <= 3:
                                    expiring_products.append({
                                        'name': product.get('product_name', 'Unknown'),
                                        'days': days_until_expiry
                                    })
                                    
                        except Exception as e:
                            print(f"Date parsing error: {e}")
                            continue
                
                # Build smart notification message
                if len(expiring_products) == 0:
                    notification_text = f"🔔 ShelfSaver Daily Check ✅\n\n🎉 Great news! No products are expiring soon.\n🍽️ Your food inventory looks good!"
                else:
                    notification_text = f"🔔 ShelfSaver Alert! ⚠️\n\n📅 You have {len(expiring_products)} product(s) expiring soon:\n\n"
                    
                    for product in expiring_products[:5]:  # Limit to 5 products
                        if product['days'] == 0:
                            notification_text += f"🚨 {product['name']} (expires TODAY!)\n"
                        elif product['days'] == 1:
                            notification_text += f"⚠️ {product['name']} (expires tomorrow)\n"
                        else:
                            notification_text += f"📅 {product['name']} (expires in {product['days']} days)\n"
                    
                    notification_text += f"\n🍽️ Check your ShelfSaver app to avoid food waste!"
                
                send_message(bot_token, user_id, notification_text)
                print(f"✅ Smart notification sent: {len(expiring_products)} expiring products")
                
                return {
                    'statusCode': 200,
                    'headers': {
                        'Access-Control-Allow-Origin': '*',
                        'Access-Control-Allow-Headers': 'Content-Type',
                        'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS'
                    },
                    'body': json.dumps({'message': 'Smart notification sent successfully!'})
                }
                
            except Exception as e:
                print(f"❌ Smart notification failed: {e}")
                return {
                    'statusCode': 500,
                    'headers': {
                        'Access-Control-Allow-Origin': '*',
                        'Access-Control-Allow-Headers': 'Content-Type',
                        'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS'
                    },
                    'body': json.dumps({'error': 'Failed to send notification'})
                }

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
                elif text.lower() == '/webapp':
                    # Send web app link
                    webapp_text = "🌐 Open ShelfSaver Web App:\nhttps://graciakaglan.github.io/ShelfSaver-AwsLambdaHackathon2025/frontend/"
                    send_message(bot_token, chat_id, webapp_text)
                elif text.lower() == '/health':
                    send_message(bot_token, chat_id, "✅ Webhook is healthy and connected!")
                    print("🏥 Health check performed")
                else:
                    send_message(bot_token, chat_id, "📸 Send a product photo for analysis!")
    
    except Exception as e:
        print(f"💥 Error: {e}")
        import traceback
        print("Traceback:", traceback.format_exc())
        return {'statusCode': 500, 'body': f'Error: {str(e)}'}
    
    return {'statusCode': 200, 'body': json.dumps({'status': 'ok', 'region': 'eu-west-3'})}


def adjust_expiry_for_demo(expiry_date):
    """Convert old dates to demo-friendly dates"""
    if expiry_date:
        try:
            # If date is in 2024, make it current/near future
            if '24' in expiry_date or '2024' in expiry_date:
                from datetime import datetime, timedelta
                
                # Make some expire today, some tomorrow, some in a week
                import random
                days_ahead = random.choice([0, 1, 2, 7])  # Today, tomorrow, 2 days, week
                
                new_date = datetime.now() + timedelta(days=days_ahead)
                return new_date.strftime('%d/%m/%y')
        except:
            pass
    return expiry_date

def save_to_database(result, chat_id):
    """Save OCR result to DynamoDB - super simple!"""
    try:
        DEMO_MODE = os.environ.get('DEMO_MODE', 'false').lower() == 'true'

        if DEMO_MODE and result.get('expiry_date'):
            result['expiry_date'] = adjust_expiry_for_demo(result['expiry_date'])
            print(f"🎬 Demo mode: Adjusted expiry date to {result['expiry_date']}")

        # Create unique ID
        product_id = str(uuid.uuid4())
        
        # Prepare item for database
        item = {
            'product_id': product_id,
            'file_id': result['file_id'],
            'product_name': result['product_name'],
            'expiry_date': result.get('expiry_date', ''),
            'barcode': result.get('barcode', ''),
            'quantity': result.get('quantity', ''),
            'confidence': result['confidence'],
            'raw_text': result['raw_text'],
            'image_s3_key': result['image_s3_key'],
            'user_id': str(chat_id),
            'created_at': datetime.now().isoformat(),
            'status': 'pending'
        }
        
        # Save to database
        table.put_item(Item=item)
        print(f"✅ Saved to database: {product_id}")
        return product_id
        
    except Exception as e:
        print(f"❌ Database save failed: {e}")
        return None

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
        save_to_database(result, chat_id)
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
                'text': "🌐 Your ShelfSaver Mini App is ready!\n\nTap the button below to view, validate and edit your scanned products:",
                'reply_markup': {
                    'inline_keyboard': [
                        [
                            {'text': '📦 Open ShelfSaver App', 'web_app': {'url': 'https://graciakaglan.github.io/ShelfSaver-AwsLambdaHackathon2025/frontend/'}}
                        ]
                    ]
                }
            }
            
            req = urllib.request.Request(url, 
                                        data=json.dumps(button_data).encode(),
                                        headers={'Content-Type': 'application/json'},
                                        method='POST')
            urllib.request.urlopen(req)
            print("✅ Web app button sent successfully")
            
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