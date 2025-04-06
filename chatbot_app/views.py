import os
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .chatbot import GymChatbot

# Initialize the chatbot as a global instance
chatbot = GymChatbot()

@csrf_exempt
def upload_text(request):
    """
    Endpoint for uploading text or a file to be processed by the chatbot.
    Supports Arabic content.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Only POST method is allowed'})
        
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
            
            # Process the file
            success = chatbot.process_file(file_path)
            
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
                
            # Process the text
            success = chatbot.process_text(text)
            
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
    Supports Arabic queries and responses.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Only POST method is allowed'})
        
    try:
        # Use proper encoding for decoding JSON with Arabic text
        data = json.loads(request.body.decode('utf-8'))
        message = data.get('message', '')
        
        if not message:
            return JsonResponse({'success': False, 'error': 'No message provided'})
        
        # Generate a response
        response = chatbot.generate_response(message)
        
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
    Endpoint for resetting the chatbot's knowledge base.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Only POST method is allowed'})
        
    try:
        # Reset the chatbot
        chatbot.delete_all_data()
        
        # Try to detect language preference from headers if available
        accept_language = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
        if 'ar' in accept_language:
            return JsonResponse({'success': True, 'message': 'تمت إعادة تعيين الروبوت المحادث بنجاح'}, 
                               json_dumps_params={'ensure_ascii': False})
        
        return JsonResponse({'success': True, 'message': 'Chatbot reset successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})