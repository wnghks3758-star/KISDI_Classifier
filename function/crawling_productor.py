from async_terms_crawling_algorithm_ver3 import *


def main():

    #약관 수집할 통신판매중개사업자 추출----------------------------------------------
    df_platform = pd.read_csv('203_category.csv', encoding='cp949')

    #필요한 행들만 남기기
    df_platform = df_platform[['사업체명','홈페이지1']]

    c_name_list = df_platform['사업체명'].to_list()
    url_list = df_platform['홈페이지1'].apply(lambda x: "https://" + str(x) if not str(x).startswith(("http://", "https://")) else str(x)).to_list()
    c_name_url_tuple = [(c_name,url) for c_name,url in zip(c_name_list,url_list)] #[(c_name1,url1),(c_name2,url2) 형태]


    # 수집 수행
    exc_c_name_list = []

    result = asyncio.run(async_crawling(c_name_url_tuple))

    for df,c_name,state in result:
        if state:
            df.to_excel(f'cate_203_약관모음/{c_name}약관.xlsx')
        else:
            exc_c_name_list.append(c_name)

    except_df = df_platform[df_platform['사업체명'].isin(exc_c_name_list)]
    except_df.to_excel("cate_203_약관모음/a.제외된_사업체.xlsx",index=False)


# def main():
#     df_platform = pd.read_csv('202_category.csv')
#     df_platform = df_platform[['사업체명','홈페이지1']]

#     # 실험하고자 하는 사업체 명
#     c_name = '아이들랩(아이고고)'
#     df_platform = df_platform[df_platform['사업체명'] == c_name]


#     print(df_platform)

#     c_name_list = df_platform['사업체명'].to_list()
#     url_list = df_platform['홈페이지1'].apply(lambda x: "https://" + str(x) if not str(x).startswith(("http://", "https://")) else str(x)).to_list()
#     c_name_url_tuple = [(c_name,url) for c_name,url in zip(c_name_list,url_list)] #[(c_name1,url1),(c_name2,url2) 형태]

#     # 수집 수행

#     result = asyncio.run(async_crawling(c_name_url_tuple))

#     for df,c_name,state in result:
#         if state:
#             df.to_excel('실험실/{}약관.xlsx'.format(c_name))


if __name__ == "__main__":
    main()