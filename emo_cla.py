import pandas as pd
import torch
from sklearn.model_selection import train_test_split
from transformers import BertTokenizer, BertForSequenceClassification, Trainer, TrainingArguments
from datasets import Dataset, DatasetDict

df = pd.read_excel('BERT_training_data.xlsx')
df = df.rename(columns={'text': 'sentence', 'label': 'emotion'})

df['sentence'] = df['sentence'].fillna('').astype(str)

emotion_to_emoji = {
    'Positive': '👍',
    'Neutral': None,
    'Negative': '👎'
}

emotion_labels = list(emotion_to_emoji.keys())
df['emotion'] = df['emotion'].apply(lambda x: emotion_labels.index(x))

train_texts, val_texts, train_labels, val_labels = train_test_split(
    df['sentence'].tolist(), df['emotion'].tolist(), test_size=0.2, random_state=42)

tokenizer = BertTokenizer.from_pretrained('bert-base-chinese')

train_encodings = tokenizer(train_texts, truncation=True, padding=True, max_length=128)
val_encodings = tokenizer(val_texts, truncation=True, padding=True, max_length=128)

train_dataset = Dataset.from_dict({'input_ids': train_encodings['input_ids'],
                                   'attention_mask': train_encodings['attention_mask'],
                                   'labels': train_labels})
val_dataset = Dataset.from_dict({'input_ids': val_encodings['input_ids'],
                                 'attention_mask': val_encodings['attention_mask'],
                                 'labels': val_labels})

datasets = DatasetDict({'train': train_dataset, 'test': val_dataset})
model = BertForSequenceClassification.from_pretrained('bert-base-chinese', num_labels=len(emotion_labels))

training_args = TrainingArguments(
    output_dir='./results',
    evaluation_strategy='epoch',
    save_strategy='epoch',
    num_train_epochs=10,
    learning_rate=2e-5,
    per_device_train_batch_size=8,
    per_device_eval_batch_size=8,
    logging_dir='./logs',
    logging_steps=10,
    save_total_limit=2,
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=datasets['train'],
    eval_dataset=datasets['test']
)

if __name__ == '__main__':
    trainer.train()

    torch.save(model.state_dict(), 'bert_emotion_model.pth')
    model.save_pretrained('bert_emotion_model')
    tokenizer.save_pretrained('bert_emotion_model')