
import pandas as pd
import numpy as np
from tqdm import tqdm


import torch
import torch.nn as nn
import torch.nn.functional as F

from transformers import AutoModel, AutoTokenizer
from sklearn.model_selection import train_test_split


class term_predictor():

  def __init__(self,model_tok_name,pth_path,to_cpu=True):

    # device 설정
    self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    # 모델 설정
    self.model = Bert_classifier(model_tok_name)
    if to_cpu:
      self.model.load_state_dict(torch.load(pth_path,map_location=torch.device('cpu')))
    else:
      self.model.load_state_dict(torch.load(pth_path))
    
    # 토크나이저 설정
    self.tokenizer = AutoTokenizer.from_pretrained(model_tok_name)



  def predict(self, sentence):
        tokens = self.tokenizer.batch_encode_plus([sentence],
                                     return_tensors = 'pt',
                                     truncation=True,
                                     padding='max_length',
                                     max_length=512
                                         )
        
        tokens.to(self.device)
        prediction = self.model(**tokens)
        prediction = F.softmax(prediction, dim=1)
        output = prediction.argmax(dim=1).item() # 확률이 가장 높은 클래스 인덱스 반환

        return output
        





class Bert_classifier(nn.Module):

  def __init__(self,pre_trained_name,drop_rate=0.5):
    super(Bert_classifier,self).__init__()

    self.bert = AutoModel.from_pretrained(pre_trained_name)
    self.drop_rate = drop_rate

    self.dr = nn.Dropout(p=drop_rate)
    self.classifier = nn.Linear(768,2)

  def forward(self, input_ids, attention_mask, token_type_ids):
    _,pooler = self.bert(input_ids=input_ids,attention_mask=attention_mask,token_type_ids=token_type_ids,return_dict =False) #batch_size,768
    output = self.dr(input=pooler)  # batch_size,768
    output = self.classifier(output) # batch)size, 2

    return output