package com.google.ai.edge.gallery.domain.skills

import com.google.ai.edge.gallery.data.SkillResult
import org.jsoup.Jsoup

class WebScraperSkill : Skill {
    override val name = "web_scraper"
    override val description = "Scrape and parse HTML from websites using Jsoup"
    override val category = SkillCategory.WEB_SCRAPER

    override suspend fun execute(parameters: Map<String, Any>): SkillResult {
        return try {
            val url = parameters["url"] as? String ?: return SkillResult.error("URL required")
            val selector = parameters["selector"] as? String ?: "body"

            val doc = Jsoup.connect(url)
                .userAgent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
                .timeout(10000)
                .get()

            val elements = doc.select(selector)
            val content = elements.joinToString("\n") { it.text() }

            if (content.isEmpty()) {
                SkillResult.error("No content found for selector: $selector")
            } else {
                SkillResult.success(content.take(5000)) // Limit to 5000 chars
            }
        } catch (e: Exception) {
            SkillResult.error("Web scraping error: ${e.message}")
        }
    }
}
