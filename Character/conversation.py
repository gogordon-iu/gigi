from transformers import AutoModelForCausalLM, AutoTokenizer


class Conversation:
    def __init__(self):
        print("Initiazling conversation ...")

        model_name = "EleutherAI/gpt-neo-125M"  # Replace with a smaller model if needed
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(model_name)

        # Assign eos_token as pad_token
        self.tokenizer.pad_token = self.tokenizer.eos_token

        self.text = []

    def response(self, input_text=None):
        if input_text is None:
            input_text = "What is the meaning of life?"
        inputs = self.tokenizer(input_text, return_tensors="pt", padding=True)

        # Pass attention_mask during generation
        output = self.model.generate(
            inputs.input_ids,
            attention_mask=inputs.attention_mask,
            max_length=50,
            pad_token_id=self.tokenizer.eos_token_id,  # Set padding token ID explicitly
            do_sample=True,
            temperature=0.5,  # Add some randomness
            top_p=0.9,        # Focus on the top 90% of probable tokens
        )

        # Decode and print the output
        print(self.tokenizer.decode(output[0], skip_special_tokens=True))
        self.text.append(self.tokenizer.decode(output[0], skip_special_tokens=True))
        
if __name__ == "__main__":
    conv = Conversation()
    conv.response()
    print(conv.text[-1])
