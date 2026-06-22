import logging
import os

import openai
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv


load_dotenv()  # no-op in Docker; loads .env for local dev
api_key = os.getenv("openai_api_key")

logger = logging.getLogger("ai")


class ExtractorModel(BaseModel):
    places: list[str]
    period: str
    street: str
    neighbourhood: str
    details: str


class OpenAIExtractor:
    def __init__(self):
        self.model = "gpt-4o-mini"
        self.valid_key = api_key is not None and api_key != "MY_OPENAI_API_KEY"
        self.client = OpenAI(api_key=api_key) if self.valid_key else None
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        # gpt-4o-mini pricing (per token)
        self.price_per_prompt_token = 0.150 / 1_000_000
        self.price_per_completion_token = 0.600 / 1_000_000

    def extract_data(self, summary: str, article_date: str) -> ExtractorModel:
        try:
            response = self.client.beta.chat.completions.parse(
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
                        """,
                    },
                    {
                        "role": "user",
                        "content": f"```{summary}```",
                    },
                ],
                response_format=ExtractorModel,
                max_tokens=1000,
            )

            # Track token usage
            if response.usage:
                self.total_prompt_tokens += response.usage.prompt_tokens
                self.total_completion_tokens += response.usage.completion_tokens
                logger.debug(
                    "Tokens — prompt: %d, completion: %d",
                    response.usage.prompt_tokens,
                    response.usage.completion_tokens,
                )

            parsed = response.choices[0].message.parsed
            if parsed is None:
                logger.warning("GPT returned no parsed response (possible refusal)")
                return ExtractorModel(
                    places=[], period="N/A", street="", neighbourhood="", details=""
                )

            return parsed

        except (openai.APIError, openai.APITimeoutError) as err:
            logger.error("OpenAI API error: %s", err)
            return ExtractorModel(
                places=[], period="N/A", street="", neighbourhood="", details=""
            )

    def log_usage_summary(self):
        prompt_cost = self.total_prompt_tokens * self.price_per_prompt_token
        completion_cost = self.total_completion_tokens * self.price_per_completion_token
        total_cost = prompt_cost + completion_cost
        logger.info(
            "GPT usage — prompt: %d tokens ($%.4f), completion: %d tokens ($%.4f), total: $%.4f",
            self.total_prompt_tokens,
            prompt_cost,
            self.total_completion_tokens,
            completion_cost,
            total_cost,
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    extractor = OpenAIExtractor()

    summary = "Уважаеми абонати, след отстраняване на авария в с.КОВАЧЕВО и възстановяване на водоснабдяването се е получило замътняване на водата в мрежата. В момента се извършва промиване на същата през наличните противопожарни хидранти. Нормалното водоснабдяване ще се възстанови до 17:00 часа. ОТ РЪКОВОДСТВОТО"

    extracted_info = extractor.extract_data(summary, "2024")
    print(f"[OpenAI] Info:\n{extracted_info.model_dump_json(indent=2)}")
    extractor.log_usage_summary()
