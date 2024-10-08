import os, openai

# from pydantic import BaseModel
from dotenv import load_dotenv


load_dotenv()
api_key = os.getenv("openai_api_key")


# class ExtractorModel(BaseModel):
#     places: list[str]
#     period: str
#     street: str
#     neighbourhood: str
#     details: str


class OpenAIExtractor:
    def __init__(self):
        openai.api_key = api_key
        self.model = "gpt-4o-mini"  # less money per call
        self.valid_key = True if api_key is not None or api_key is not "MY_OPENAI_API_KEY" else False
        # self.model = "gpt-4o" # too expensive
        # self.model = "gpt-3.5-turbo",  # or gpt-4 if you have access to it

    def extract_data(self, summary: str, article_date: str) -> dict:
        # Update the model and use the Chat API for the new version
        response = openai.ChatCompletion.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": f"""
                    Извади населените места, периода в който е прекъснато водоснабдяването, улица или квартал ако са налични, както и допълнителни детайли като помпена станция или фирма от текста предоставен от потребителя. 
                    
                    Правила за формата на отговора:
                    `places` - само населеното място заедно с абревиатурата за град или село преди името на мястото ; при наличието на имена на улици, но не и населено място, в повечето случаи това е "гр. Пазарджик" ; не ни трябва община ; примери: "с. Мало Конаре", "гр. Пазарджик"
                    `period` - HH:mm и dd.MM.YYYY формат без абревиатури и дни от седмицата ; ако има крайна дата относно възстановяване или прекъсване различна от '{article_date}' само тогава я пиши ; ако няма час или дата напиши 'не е указан' ; пример само с часове: "09:00 - 12:00", пример с часове и наличието на крайна дата различна от тази за аварията в текста: "09:00 - 12:00 (02.09.2024)", пример само с час на възстановяване: "- 17:00",  пример само с час на прекъсване: "10:00 -"
                    `street` - ако има улица я запиши с абревиатурата "ул.", ако има и номер на улицата запиши и него ; пример: "ул. Георги Бенковски №123"
                    `neighbourhood` - ако има квартал го запиши с абревиатурата "кв." ; пример: "кв. Младост"
                    `details` - детайли които сметнеш че биха били важни, без "От Ръководството" ; пример: "Ремонт на ПС от Електроразпределение Юг"
                    
                    Върни информацията във формат (стриктно спазвай описаните правила):
                    ```json
                    {{
                        "places": ["место1", "место2", ...] (спазвай формата зададен в примерите от правилата),
                        "period": "начален час - краен час (винаги слагай в скоби дати ако са налични и различни от '{article_date}' според инструкциите)",
                        "street": "улица и номер",
                        "neighbourhood": "квартал",
                        "details": "помпена станция или фирма"
                    }}
                    ```
                    """,
                },
                {
                    "role": "user",
                    "content": f"""
                    ```{summary}```
                    """,
                },
            ],
            response_format={"type": "json_object"},
            max_tokens=1000,
        )

        # Extract the content of the assistant's response
        extracted_info = response["choices"][0]["message"]["content"]
        return extracted_info


if __name__ == "__main__":
    extractor = OpenAIExtractor()

    summary = "Поради авария на уличен водопровод, е прекъснато водоподаването в с. Дъбравите от 01,00 часа . Водоподаването ще бъде възстановено до 17,00 ч. на 05.08.2024 г. / четвъртък/. От Ръководството"
    # summary = "Поради авария на уличен водопровод, е прекъснато водоподаването в с. Малко Белово от 22,00 часа на 04.08.2024 г. / сряда . Водоподаването ще бъде възстановено до 12,00 ч. на 05.08.2024 г. / четвъртък/. От Ръководството"
    # summary = "Уважаеми абонати, след отстраняване на авария в с.КОВАЧЕВО и възстановяване на водоснабдяването се е получило замътняване на водата в мрежата. В момента се извършва промиване на същата през наличните противопожарни хидранти. Нормалното водоснабдяване ще се възстанови до 17:00 часа. ОТ РЪКОВОДСТВОТО"

    extracted_info = extractor.extract_data(summary)
    print(f"[OpenAI] Info:\n{extracted_info}")
