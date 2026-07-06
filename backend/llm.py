from openai import OpenAI


class LLM:
    def __init__(self, base_url, api_key, model, system_prompt):
        self.client = OpenAI(base_url=base_url, api_key=api_key or "ollama", timeout=60)
        self.model = model
        self.messages = [{"role": "system", "content": system_prompt}]

    def ask(self, text):
        self.messages.append({"role": "user", "content": text})
        response = self.client.chat.completions.create(
            model=self.model, messages=self.messages
        )
        reply = (response.choices[0].message.content or "").strip()
        self.messages.append({"role": "assistant", "content": reply})
        if len(self.messages) > 13:
            self.messages = [self.messages[0]] + self.messages[-12:]
        return reply
