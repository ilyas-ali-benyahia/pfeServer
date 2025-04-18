import os
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .chatbot import GymChatbot

# Initialize the chatbot as a global instance
chatbot = GymChatbot()

def get_user_id_from_request(request):
    """
    Extract user ID from the Supabase auth token in the request.
    """
    try:
        # Get the Authorization header (Bearer token)
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return None
            
        # Extract the token
        token = auth_header.split(' ')[1]
        
        # Get user ID from token
        user_id = chatbot.get_user_from_token(token)
        return user_id
    except Exception as e:
        print(f"Error extracting user ID: {e}")
        return None

@csrf_exempt
def upload_text(request):
    """
    Endpoint for uploading text or a file to be processed by the chatbot.
    Requires Supabase authentication.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Only POST method is allowed'})
    
    # Get user ID from Supabase auth token
    user_id = get_user_id_from_request(request)
    if not user_id:
        return JsonResponse({'success': False, 'error': 'Authentication required'}, status=401)
    
    try:
        # Check if it's a file upload
        if request.FILES.get('file'):
            uploaded_file = request.FILES.get('file')
            
            # Create temp directory if it doesn't exist
            temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp')
            os.makedirs(temp_dir, exist_ok=True)
            
            # Save the file temporarily
            file_path = os.path.join(temp_dir, uploaded_file.name)
            
            with open(file_path, 'wb+') as destination:
                for chunk in uploaded_file.chunks():
                    destination.write(chunk)
            
            # Process the file with user_id
            success = chatbot.process_file(file_path, user_id)
            
            # Clean up
            if os.path.exists(file_path):
                os.remove(file_path)
                
            if success:
                return JsonResponse({'success': True, 'message': 'File processed successfully'})
            else:
                return JsonResponse({'success': False, 'error': 'Error processing file'})
                
        # Check if it's a JSON with text
        elif request.content_type == 'application/json':
            # Use json.loads with proper encoding to handle Arabic
            data = json.loads(request.body.decode('utf-8'))
            text = data.get('text', '')
            
            if not text:
                return JsonResponse({'success': False, 'error': 'No text provided'})
                
            # Process the text with user_id
            success = chatbot.process_text(text, user_id)
            
            if success:
                # Detect if the text was primarily Arabic for the response message
                is_arabic = any('\u0600' <= c <= '\u06FF' for c in text[:100])
                
                if is_arabic:
                    return JsonResponse({'success': True, 'message': 'تمت معالجة النص بنجاح'})
                else:
                    return JsonResponse({'success': True, 'message': 'Text processed successfully'})
            else:
                if any('\u0600' <= c <= '\u06FF' for c in text[:100]):
                    return JsonResponse({'success': False, 'error': 'حدث خطأ أثناء معالجة النص'})
                else:
                    return JsonResponse({'success': False, 'error': 'Error processing text'})
        
        else:
            return JsonResponse({'success': False, 'error': 'No file or text provided'})
            
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@csrf_exempt
def chat(request):
    """
    Endpoint for chatting with the initialized chatbot.
    Requires Supabase authentication.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Only POST method is allowed'})
    
    # Get user ID from Supabase auth token
    user_id = get_user_id_from_request(request)
    if not user_id:
        return JsonResponse({'success': False, 'error': 'Authentication required'}, status=401)
        
    try:
        # Use proper encoding for decoding JSON with Arabic text
        data = json.loads(request.body.decode('utf-8'))
        message = data.get('message', '')
        
        if not message:
            return JsonResponse({'success': False, 'error': 'No message provided'})
        
        # Generate a response with user_id
        response = chatbot.generate_response(message, user_id)
        
        return JsonResponse({'success': True, 'response': response}, json_dumps_params={'ensure_ascii': False})
        
    except Exception as e:
        # Check if the original query was in Arabic to respond accordingly
        try:
            original_message = json.loads(request.body.decode('utf-8')).get('message', '')
            is_arabic = any('\u0600' <= c <= '\u06FF' for c in original_message)
            
            if is_arabic:
                return JsonResponse({'success': False, 'error': 'حدث خطأ أثناء معالجة استفسارك'}, 
                                   json_dumps_params={'ensure_ascii': False})
        except:
            pass
            
        return JsonResponse({'success': False, 'error': str(e)})

@csrf_exempt
def reset(request):
    """
    Endpoint for resetting the chatbot's knowledge base for a specific user.
    Requires Supabase authentication.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Only POST method is allowed'})
    
    # Get user ID from Supabase auth token
    user_id = get_user_id_from_request(request)
    if not user_id:
        return JsonResponse({'success': False, 'error': 'Authentication required'}, status=401)
        
    try:
        # Reset the chatbot for this user only
        chatbot.delete_all_data(user_id)
        
        # Try to detect language preference from headers if available
        accept_language = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
        if 'ar' in accept_language:
            return JsonResponse({'success': True, 'message': 'تمت إعادة تعيين الروبوت المحادث بنجاح'}, 
                               json_dumps_params={'ensure_ascii': False})
        
        return JsonResponse({'success': True, 'message': 'Chatbot reset successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
