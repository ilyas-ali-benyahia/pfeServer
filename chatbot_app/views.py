import os
import json
import traceback
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .chatbot import GymChatbot

# Initialize the chatbot as a global instance
chatbot = GymChatbot()

@csrf_exempt
def upload_text(request):
    """
    Enhanced endpoint for uploading text or a file to be processed by the chatbot.
    Improved error handling and multilingual support.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Only POST method is allowed'}, status=405)
        
    try:
        # Check if it's a file upload
        if request.FILES.get('file'):
            uploaded_file = request.FILES.get('file')
            
            # Validate file size (limit to 10MB)
            if uploaded_file.size > 10 * 1024 * 1024:
                return JsonResponse({
                    'success': False, 
                    'error': 'File too large. Maximum size is 10MB.'
                }, status=413)
            
            # Validate file extension
            allowed_extensions = ['.txt', '.md', '.csv', '.json', '.html', '.xml', '.yaml', '.yml', '.py', '.js', '.doc', '.docx']
            file_ext = os.path.splitext(uploaded_file.name)[1].lower()
            
            if file_ext not in allowed_extensions:
                return JsonResponse({
                    'success': False, 
                    'error': f'Unsupported file type. Allowed types: {", ".join(allowed_extensions)}'
                }, status=415)
            
            # Create temp directory if it doesn't exist
            temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp')
            os.makedirs(temp_dir, exist_ok=True)
            
            # Save the file temporarily with a safe filename
            safe_filename = os.path.basename(uploaded_file.name)
            file_path = os.path.join(temp_dir, safe_filename)
            
            with open(file_path, 'wb+') as destination:
                for chunk in uploaded_file.chunks():
                    destination.write(chunk)
            
            # Process the file
            success = chatbot.process_file(file_path)
            
            # Clean up
            if os.path.exists(file_path):
                os.remove(file_path)
                
            if success:
                # Detect language for response
                is_arabic = any('\u0600' <= c <= '\u06FF' for c in request.META.get('HTTP_ACCEPT_LANGUAGE', '')[:10])
                
                if is_arabic:
                    return JsonResponse({'success': True, 'message': 'تمت معالجة الملف بنجاح'}, 
                                       json_dumps_params={'ensure_ascii': False})
                else:
                    return JsonResponse({'success': True, 'message': 'File processed successfully'})
            else:
                return JsonResponse({'success': False, 'error': 'Error processing file'}, status=422)
                
        # Check if it's a JSON with text
        elif request.content_type == 'application/json':
            try:
                # Use json.loads with proper encoding to handle Arabic
                data = json.loads(request.body.decode('utf-8'))
                text = data.get('text', '')
                
                if not text:
                    return JsonResponse({'success': False, 'error': 'No text provided'}, status=400)
                
                # Limit text size (10MB max)
                if len(text.encode('utf-8')) > 10 * 1024 * 1024:
                    return JsonResponse({
                        'success': False, 
                        'error': 'Text too large. Maximum size is 10MB.'
                    }, status=413)
                    
                # Process the text
                success = chatbot.process_text(text)
                
                if success:
                    # Detect if the text was primarily Arabic for the response message
                    is_arabic = chatbot.detect_language(text) == 'ar'
                    
                    if is_arabic:
                        return JsonResponse({'success': True, 'message': 'تمت معالجة النص بنجاح'}, 
                                          json_dumps_params={'ensure_ascii': False})
                    else:
                        return JsonResponse({'success': True, 'message': 'Text processed successfully'})
                else:
                    if chatbot.detect_language(text) == 'ar':
                        return JsonResponse({'success': False, 'error': 'حدث خطأ أثناء معالجة النص'}, 
                                           json_dumps_params={'ensure_ascii': False}, status=422)
                    else:
                        return JsonResponse({'success': False, 'error': 'Error processing text'}, status=422)
            except json.JSONDecodeError:
                return JsonResponse({'success': False, 'error': 'Invalid JSON format'}, status=400)
        
        else:
            return JsonResponse({'success': False, 'error': 'No file or text provided'}, status=400)
            
    except Exception as e:
        print(f"Error in upload_text: {e}")
        print(traceback.format_exc())
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@csrf_exempt
def chat(request):
    """
    Enhanced endpoint for chatting with the initialized chatbot.
    Improved error handling and message preprocessing.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Only POST method is allowed'}, status=405)
        
    try:
        # Use proper encoding for decoding JSON with Arabic text
        try:
            data = json.loads(request.body.decode('utf-8'))
            message = data.get('message', '')
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON format'}, status=400)
        
        if not message:
            return JsonResponse({'success': False, 'error': 'No message provided'}, status=400)
        
        # Check message length
        if len(message) > 5000:
            # Detect language for appropriate error message
            is_arabic = chatbot.detect_language(message) == 'ar'
            
            if is_arabic:
                return JsonResponse({
                    'success': False, 
                    'error': 'الرسالة طويلة جدًا. الحد الأقصى هو 5000 حرف.'
                }, json_dumps_params={'ensure_ascii': False}, status=413)
            else:
                return JsonResponse({
                    'success': False, 
                    'error': 'Message too long. Maximum length is 5000 characters.'
                }, status=413)
        
        # Generate a response
        response = chatbot.generate_response(message)
        
        # Return the response with appropriate content type
        return JsonResponse(
            {'success': True, 'response': response, 'language': chatbot.detect_language(message)}, 
            json_dumps_params={'ensure_ascii': False}
        )
        
    except Exception as e:
        print(f"Error in chat: {e}")
        print(traceback.format_exc())
        
        # Check if the original query was in Arabic to respond accordingly
        try:
            original_message = json.loads(request.body.decode('utf-8')).get('message', '')
            is_arabic = chatbot.detect_language(original_message) == 'ar'
            
            if is_arabic:
                return JsonResponse({
                    'success': False, 
                    'error': 'حدث خطأ أثناء معالجة استفسارك. يرجى المحاولة مرة أخرى.'
                }, json_dumps_params={'ensure_ascii': False}, status=500)
        except:
            pass
            
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@csrf_exempt
def reset(request):
    """
    Enhanced endpoint for resetting the chatbot's knowledge base.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Only POST method is allowed'}, status=405)
        
    try:
        # Reset the chatbot
        chatbot.delete_all_data()
        
        # Try to detect language preference
        accept_language = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
        content_type = request.content_type
        
        # Check for Arabic preference in Accept-Language header
        if 'ar' in accept_language:
            return JsonResponse({
                'success': True, 
                'message': 'تمت إعادة تعيين الروبوت المحادث بنجاح'
            }, json_dumps_params={'ensure_ascii': False})
        
        # If there's a JSON body, check language preference there
        if content_type == 'application/json':
            try:
                data = json.loads(request.body.decode('utf-8'))
                lang_pref = data.get('language', '')
                
                if lang_pref == 'ar':
                    return JsonResponse({
                        'success': True, 
                        'message': 'تمت إعادة تعيين الروبوت المحادث بنجاح'
                    }, json_dumps_params={'ensure_ascii': False})
            except:
                pass
        
        # Default to English
        return JsonResponse({'success': True, 'message': 'Chatbot reset successfully'})
        
    except Exception as e:
        print(f"Error in reset: {e}")
        print(traceback.format_exc())
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@csrf_exempt
def status(request):
    """
    New endpoint to check chatbot status and loaded content.
    """
    if request.method != 'GET':
        return JsonResponse({'success': False, 'error': 'Only GET method is allowed'}, status=405)
        
    try:
        # Get basic status information
        status_info = {
            'initialized': chatbot.is_initialized,
            'knowledge_chunks': len(chatbot.knowledge_base),
            'conversation_history': len(chatbot.chat_history),
            'ready': True
        }
        
        # Try to detect language preference
        accept_language = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
        
        # Check for Arabic preference
        if 'ar' in accept_language:
            status_info['message'] = 'الروبوت المحادث جاهز للاستخدام'
            return JsonResponse(status_info, json_dumps_params={'ensure_ascii': False})
        
        # Default to English
        status_info['message'] = 'Chatbot is ready to use'
        return JsonResponse(status_info)
        
    except Exception as e:
        print(f"Error in status: {e}")
        print(traceback.format_exc())
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
