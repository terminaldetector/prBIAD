package com.google.ai.edge.gallery.domain.skills

import android.content.Context
import com.google.ai.edge.gallery.data.SkillResult
import com.google.ai.edge.gallery.domain.mcp.MCPClientImpl
import com.google.ai.edge.gallery.domain.mcp.MCPResponse

class NativeActionSkillImpl(private val context: Context) : Skill {
    override val name = "native_actions"
    override val description = "Execute native device actions (SMS, Alarms, App Launching, etc)"
    override val category = SkillCategory.NATIVE_ACTION
    
    private val mcpClient = MCPClientImpl(context)

    override suspend fun execute(parameters: Map<String, Any>): SkillResult {
        return try {
            val actionType = parameters["action"] as? String ?: return SkillResult.error("No action specified")
            val actionParams = parameters["params"] as? Map<String, Any> ?: emptyMap()

            val response = mcpClient.executeAction(actionType, actionParams)
            
            if (response.success) {
                SkillResult.success(response.result?.toString() ?: "Action executed")
            } else {
                SkillResult.error(response.error ?: "Unknown error")
            }
        } catch (e: Exception) {
            SkillResult.error("Error executing native action: ${e.message}")
        }
    }
}
