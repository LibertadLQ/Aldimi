from backend.main import chat, ChatRequest

print('Test 1: normal message with debug')
print(chat(ChatRequest(mensaje='hola', ciu=None, debug=True)))

print('\nTest 2: emotional risk with debug')
print(chat(ChatRequest(mensaje='me quiero morir', ciu=None, debug=True)))
