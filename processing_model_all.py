from processing_model_201 import processer_201
from processing_model_202 import processer_202
from processing_model_203 import processer_203


def main():
    input_file_name = str(input('분류를 수행할 파일명을 경로와 함께 입력해주세요(csv형태):'))
    output_file_name_201 = str(input('201 업태 분류 모델의 결과 파일명을 경로와 함께 입력해주세요(xlsx형태):'))
    output_file_name_202 = str(input('202 업태 분류 모델의 결과 파일명을 경로와 함께 입력해주세요(xlsx형태):'))
    output_file_name_203 = str(input('203 업태 분류 모델의 결과 파일명을 경로와 함께 입력해주세요(xlsx형태):'))

    processer_201(input_file_name,output_file_name_201)
    processer_202(input_file_name,output_file_name_202)
    processer_203(input_file_name,output_file_name_203)



if __name__ == '__main__':
    main()