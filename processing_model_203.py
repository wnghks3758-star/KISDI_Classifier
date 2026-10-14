import function.keyword_finder_v5 as kf
from function.async_terms_crawling_algorithm_ver3 import *
import function.bert_classifier as bc
import function.find_app_down_v2 as fa
from tqdm import tqdm
import threading




def main():
    # input_file_name = str(input('분류를 수행할 파일명을 경로와 함께 입력해주세요(csv형태):'))
    input_file_name = '분류필요데이터/preprocessed_website_url.csv'
    # output_file_name_203 = str(input('203 업태 분류 모델의 결과 파일명을 경로와 함께 입력해주세요(xlsx형태):'))
    output_file_name_203 = 'kisdi_test-203_for_test2.xlsx'




    processer_203(input_file_name,output_file_name_203)



# 웹페이지 분류



def classifier(c_name,homepage,processer,term_predictor,app_finder):
    bizno,cate,find_word = processer.main_processer(c_name,homepage)




    # 각 cate를 어떻게 처리할지
    # 확인필요, 통신판매자의 경우 약관탐색 수행해야 함

    #-------------------------------확인 필요 통신판매자의 경우-----------------------------#
    if cate != 'not-203':
        return bizno,cate,find_word

    terms = return_terms(c_name,homepage,['지적','저작','서비스','영리','콘텐츠','컨텐츠'])
        #terms가 None일 경우 앱소개 페이지 판단 하고, 아닐 경우 확인 필요로 남겨둬야 할 듯

    #-------------------------terms가 None일 경우-------------------------------#
    # 약관이 없다는 가정 하에 일반 웹사이트로 분류
    # 추가적으로 앱소개 페이지 탐지 해야함 @@@@@@@@@@@@@@@
    if terms is None or terms.empty:    
        try:
            c_name, state = app_finder.finding(c_name,homepage)
        except:
            app_finder.reset_driver()
            state = None
        if state == 'download_url':
            return bizno,'앱소개',None
        else:
            return bizno,'Not-203',None

    #-------------------------terms가 None이 아닐 경우----------------------------#
    # 1. 약관 분석 결과 중개자 -> 중개자로 분류 
    # 2. 약관 분석 결과 중개자 아님
    #  2-1. 통신판매업자의 경우 -> 일반 통신판매자로 분류
    #  2-2. 확인 필요의 경우 -> 일반 웹사이트로 분류(? 약관이 있는데 중개자가 아니면 일반 웹사이트일듯?)


    sum = 0
    # total_len = len(terms['sentence'])
    for sentence in terms['sentence']:
        sum += term_predictor.predict(sentence)

    # error_rate = total_len*0.02 # 이걸 어떻게 처리할지는 논의가 필요함 (일단은 문장 수 *0.02(오류율) → 예상 오류 개수 를 넘으면 1 아니면 0)

    # sum 값이 0이 아닌 경우
    if sum > 1:
        return bizno,'203','Bert'


    try:
        c_name, state = app_finder.finding(c_name, homepage) 
    except:
        app_finder.reset_driver()
        state = None  # 예외 발생 시 state 기본값 설정

    # state가 download_url인 경우 처리
    if state == 'download_url':
        return bizno,'앱소개',None

    else:
        return bizno,cate,None


    
def processer_203(input_file_name,output_file_name):
    #---------------------------필요 class 불러오기-------------------------#
    # 키워드 검색 알고리즘
    processer = kf.keyword_finder('필요파일/keyword_dict_203.pickle',None,203)
    # 약관 분석 모델 
    term_predictor = bc.term_predictor("klue/roberta-base",'필요파일/classifier-kor-base_203.pth')
    app_finder = fa.app_finder()

    #-----------------------df 받아서 전처리-------------------------#
    df = pd.read_csv(input_file_name, encoding='cp949')
    df_n = df[:20]
    df_n = df_n[['사업체명','홈페이지1']] # 필요한 행들만 남겨 놓고




    #--------------------------분류 수행-----------------------------#
    new_df = []


    tqdm.pandas()  # tqdm을 pandas의 기능으로 확장

    for row in tqdm(df_n.itertuples(index=False), total=len(df_n)):
        c_name, homepage = row.사업체명, row.홈페이지1  # 열 이름에 맞게 변경
        bizno, cate,find_word = run_with_timeout(
            classifier, 
            args=(c_name, homepage, processer, term_predictor, app_finder),
            timeout= 600  # 8분 제한
        )

        new_df.append({'사업체명': c_name,'사업자등록번호': bizno , '홈페이지1': homepage, 'cate': cate, 'keyword':find_word})

    # dataframe to excel
    new_df = pd.DataFrame(new_df)
    new_df.to_excel(output_file_name, index=False)




def run_with_timeout(target, args=(), timeout=600):
    """
    특정 함수를 지정된 시간(timeout) 내에 실행하고,
    시간이 초과되면 강제 종료하는 함수.
    """
    result = [None]  # 리스트 사용 (mutable object)

    def wrapper():
        result[0] = target(*args)  # 리스트 요소를 수정


    thread = threading.Thread(target=wrapper)
    thread.start()
    thread.join(timeout)  # 지정된 시간 동안 실행

    if thread.is_alive():  # 10분이 지나도 실행 중이라면 종료
        print("시간 초과로 해당 항목을 건너뜁니다.")
        return None,'오류',None  # 시간 초과 시 반환 값

    return result[0]  # 실행 결과 반환


if __name__ == '__main__':
    main()



