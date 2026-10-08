import tkinter as tk
from tkinter import ttk, scrolledtext
from concurrent.futures import ThreadPoolExecutor
import queue
import httpx

def main():
    root = tk.Tk()
    root.title('CineBot AI — simulador de conversa')
    root.geometry('760x580')
    values = {}
    for label, default, secret in [('API', 'http://127.0.0.1:8000', False), ('Token', 'change-me', True), ('Usuário', 'demo-user', False)]:
        frame = ttk.Frame(root)
        frame.pack(fill='x', padx=12, pady=4)
        ttk.Label(frame, text=label, width=10).pack(side='left')
        value = tk.StringVar(value=default)
        values[label] = value
        ttk.Entry(frame, textvariable=value, show='*' if secret else '').pack(side='left', fill='x', expand=True)
    history = scrolledtext.ScrolledText(root, wrap='word', state='disabled')
    history.pack(fill='both', expand=True, padx=12, pady=10)
    message = tk.StringVar()
    ttk.Entry(root, textvariable=message).pack(fill='x', padx=12)
    results = queue.Queue()
    pool = ThreadPoolExecutor(max_workers=1)

    def display(text):
        history.configure(state='normal')
        history.insert('end', text + '\n\n')
        history.see('end')
        history.configure(state='disabled')

    def send():
        text = message.get().strip()
        if not text:
            return
        url, token, user = (values[k].get() for k in ('API','Token','Usuário'))
        message.set('')
        display('Você: ' + text)
        button.configure(state='disabled')
        def request():
            try:
                r = httpx.post(url.rstrip('/')+'/chat', headers={'Authorization':'Bearer '+token}, json={'user_id':user,'message':text}, timeout=180)
                r.raise_for_status()
                results.put('CineBot: '+r.json()['answer'])
            except Exception as exc:
                results.put('Falha na conexão/API: '+type(exc).__name__)
        pool.submit(request)

    def poll():
        try:
            display(results.get_nowait())
            button.configure(state='normal')
        except queue.Empty:
            pass
        root.after(100, poll)

    button = ttk.Button(root, text='Enviar', command=send)
    button.pack(pady=10)
    root.bind('<Return>', lambda event: send() if str(button['state']) != 'disabled' else None)
    display('Modo demo não consulta catálogos. Use /esquecer para apagar o histórico.')
    poll()
    root.mainloop()
    pool.shutdown(wait=False)

if __name__ == '__main__':
    main()
