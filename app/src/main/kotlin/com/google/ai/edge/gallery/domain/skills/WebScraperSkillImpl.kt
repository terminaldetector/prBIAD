package com.google.ai.edge.gallery.domain.skills

import com.google.ai.edge.gallery.data.SkillResult
import org.jsoup.Jsoup
import java.util.concurrent.TimeUnit

class WebScraperSkillImpl : Skill {
    override val name = "web_scraper"
    override val description = "Scrape and parse HTML from websites using Jsoup"
    override val category = SkillCategory.WEB_SCRAPER

    override suspend fun execute(parameters: Map<String, Any>): SkillResult {
        return try {
            val url = parameters["url"] as? String ?: return SkillResult.error("URL required")
            val selector = parameters["selector"] as? String ?: "body"
            val maxLength = (parameters["maxLength"] as? Number)?.toInt() ?: 5000

            val doc = Jsoup.connect(url)
                .userAgent("Mozilla/5.0 (Android 12; Mobile)")
                .timeout(15000)
                .get()

            val elements = doc.select(selector)
            if (elements.isEmpty) {
                return SkillResult.error("No content found for selector: $selector")
            }

            val content = elements.joinToString("\n\n") { element ->
                element.text().trim()
            }.take(maxLength)

            if (content.isEmpty()) {
                SkillResult.error("No text content extracted")
            } else {
                SkillResult.success(content)
            }
        } catch (e: Exception) {
            SkillResult.error("Web scraping failed: ${e.message}")
        }
    }
}
