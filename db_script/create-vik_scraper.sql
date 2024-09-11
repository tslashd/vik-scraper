-- Dumping database structure for vik_scraper
CREATE DATABASE IF NOT EXISTS `vik_scraper` /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci */ /*!80016 DEFAULT ENCRYPTION='N' */;
USE `vik_scraper`;

-- Dumping structure for table vik_scraper.vik_gpt_4o_mini
CREATE TABLE IF NOT EXISTS `vik_gpt_4o_mini` (
  `post_id` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT 'ID на съобщението в сайта',
  `title` varchar(256) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT 'Заглавие на съобщението в сайта',
  `location` varchar(256) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL COMMENT 'Града или селото в което има авария',
  `period` varchar(256) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL COMMENT 'Периодът обявен за аварията',
  `author` varchar(256) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT 'Авторът на съобщението в сайта',
  `summary` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT 'Пълният текст от който сме извлекли информацията',
  `category` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT 'Категорията която е сложена за съобщението от сайта',
  `ai_extract` tinyint NOT NULL COMMENT 'Минало ли е през ChatGPT за извличане на данни?',
  `page` smallint NOT NULL COMMENT 'Страницата на която е било съобщението',
  `total_pages` smallint NOT NULL COMMENT 'Общият брой страници при извличане',
  `comments` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci COMMENT 'Коментарите от съобщението',
  `date_added` datetime NOT NULL DEFAULT (now()),
  `article_date` date DEFAULT NULL,
  `date_updated` datetime NOT NULL DEFAULT (now()),
  UNIQUE KEY `post_id` (`post_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Dumping structure for table vik_scraper.vik_gpt_4o_mini_edited
CREATE TABLE IF NOT EXISTS `vik_gpt_4o_mini_edited` (
  `post_id` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT 'ID на съобщението в сайта',
  `title` varchar(256) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT 'Заглавие на съобщението в сайта',
  `location` varchar(256) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL COMMENT 'Града или селото в което има авария',
  `period` varchar(256) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL COMMENT 'Периодът обявен за аварията',
  `author` varchar(256) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT 'Авторът на съобщението в сайта',
  `summary` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT 'Пълният текст от който сме извлекли информацията',
  `category` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT 'Категорията която е сложена за съобщението от сайта',
  `ai_extract` tinyint NOT NULL COMMENT 'Минало ли е през ChatGPT за извличане на данни?',
  `page` smallint NOT NULL COMMENT 'Страницата на която е било съобщението',
  `total_pages` smallint NOT NULL COMMENT 'Общият брой страници при извличане',
  `comments` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci COMMENT 'Коментарите от съобщението',
  `date_added` datetime NOT NULL DEFAULT (now()),
  `article_date` date DEFAULT NULL,
  UNIQUE KEY `summary` (`summary`(750)),
  KEY `Foreign Key - post_id` (`post_id`),
  CONSTRAINT `Foreign Key - post_id` FOREIGN KEY (`post_id`) REFERENCES `vik_gpt_4o_mini` (`post_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Таблица в коята се местят съобщенията които са били променени след началното им извличане от сайта';
