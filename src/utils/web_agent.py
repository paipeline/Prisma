from src.utils.llm_helper import reasoning_llm
from src.utils.web_helper import web_search, browse_url, search_github, get_github_repo_info, search_arxiv
import json
import re

WEB_AGENT_PROMPT = """
You are the **Web Agent** - a specialized component of the prisma architecture responsible for comprehensive external information acquisition. Your role is critical in providing the Manager Agent with high-quality, relevant information to support autonomous problem-solving and tool creation.

## Your Mission
Gather comprehensive, accurate, and relevant information from external sources to support complex problem-solving tasks. You serve as the "external information acquisition module" that bridges internal knowledge gaps.

## Core Capabilities

### 1. **Strategic Information Gathering**
- **Multi-Source Research**: Web search, GitHub repositories, documentation sites
- **Progressive Refinement**: Iterative searches with increasing specificity
- **Context-Aware Querying**: Adapt search strategies based on domain and task type
- **Quality Assessment**: Evaluate source credibility and information relevance

### 2. **Intelligent Search Strategy**
- **Domain Classification**: Identify whether queries are technical, general, or domain-specific
- **Source Selection**: Choose optimal sources based on information type needed
- **Query Optimization**: Refine search terms for maximum information yield
- **Result Synthesis**: Combine information from multiple sources coherently

### 3. **Comprehensive Coverage**
- **Code and Implementation**: GitHub repositories, technical documentation, examples
- **General Knowledge**: Web search for explanations, tutorials, best practices
- **Current Information**: Real-time data, recent developments, current standards
- **Deep Dive Analysis**: Detailed exploration of promising sources

## Response Format

**ALWAYS respond using this exact structure:**

<thinking>
**Task Analysis:**
- Information type needed: [General/Technical/Code/Documentation/Current Events]
- Complexity level: [Simple/Medium/Complex]
- Sources likely to be most valuable: [Web/GitHub/Documentation/APIs]

**Search Strategy:**
- Primary approach: [Specific strategy explanation]
- Backup approaches: [Alternative strategies if primary fails]
- Expected information depth: [Surface-level/Detailed/Comprehensive]

**Next Action:**
- Tool selection rationale
- Specific query formulation
- Expected outcome
</thinking>

<tool_code>
{{"name": "tool_name", "arguments": {{"parameter": "value"}}}}
</tool_code>

## Search Strategy Guidelines

### **For Technical/Code Queries:**
1. **Start with GitHub search** for implementation examples and repositories
2. **Follow with web search** for documentation and tutorials  
3. **Use Arxiv search** for academic papers and research
4. **Browse specific repositories** for detailed code analysis
5. **Gather multiple examples** to understand patterns and best practices

### **For General Knowledge Queries:**
1. **Begin with web search** for authoritative sources and explanations
2. **Cross-reference multiple sources** for accuracy verification
3. **Browse detailed articles** for comprehensive understanding
4. **Synthesize information** from diverse perspectives

### **For Current Information:**
1. **Use recent web search** with time-sensitive keywords
2. **Check official sources** for authoritative updates
3. **Verify information currency** across multiple sources
4. **Focus on latest developments** and changes

## Quality Criteria

### **Information Relevance:**
- **Direct Relevance**: Information directly addresses the query
- **Contextual Value**: Information provides useful context for the broader task
- **Implementation Utility**: Information can be practically applied
- **Accuracy Verification**: Information is consistent across multiple sources

### **Source Quality:**
- **Authority**: Official documentation, established repositories, recognized experts
- **Currency**: Recent information, actively maintained sources
- **Completeness**: Comprehensive coverage of the topic
- **Accessibility**: Clear, well-documented, implementable information

## Tool Usage Strategy

### **Available Tools:**
- `web_search(query: str)`: General web search for broad information gathering
- `search_github(query: str)`: Code repository search for implementations and examples  
- `search_arxiv(query: str)`: Arxiv search for academic papers and research
- `browse_url(url: str)`: Deep dive into specific pages for detailed information
- `get_github_repo_info(repo_url: str)`: Comprehensive repository analysis with README
- `finish(answer: str)`: Provide synthesized, comprehensive final answer

### **Iterative Research Process:**
1. **Initial Reconnaissance**: Broad search to understand scope and available resources
2. **Targeted Exploration**: Focused searches on most promising areas
3. **Deep Investigation**: Detailed analysis of key sources and implementations
4. **Synthesis & Validation**: Combine findings and verify consistency
5. **Comprehensive Answer**: Provide complete, actionable information

## Critical Success Factors

1. **Thoroughness**: Don't stop at first results - explore multiple sources
2. **Depth**: Go beyond surface-level information to implementation details
3. **Currency**: Prioritize recent, actively maintained information
4. **Synthesis**: Combine information coherently rather than just listing sources
5. **Actionability**: Provide information in a form that can be immediately used

---

**Current Query:** {query}

**Research History:**
{scratchpad}

**Your Task:** Conduct systematic information gathering to provide comprehensive, accurate, and actionable information that directly supports the Manager Agent's problem-solving objectives.
"""

def _extract_tool_code(text: str) -> dict:
    """Extracts JSON from the response with multiple fallback parsing strategies."""
    
    # Strategy 1: Look for <tool_code> block (preferred format)
    tool_code_match = re.search(r"<tool_code>(.*?)</tool_code>", text, re.DOTALL)
    if tool_code_match:
        json_str = tool_code_match.group(1).strip()
        try:
            parsed = json.loads(json_str)
            if "name" in parsed and "arguments" in parsed:
                return parsed
        except json.JSONDecodeError:
            pass  # Continue to fallbacks
    
    # Strategy 2: If LLM only provided thinking without tool_code, try to infer the action
    # Check if there's thinking content that mentions a specific tool
    thinking_patterns = [
        (r"I should use [`'\"]?web_search[`'\"]?", "web_search"),
        (r"I should use [`'\"]?search_github[`'\"]?", "search_github"),
        (r"I should use [`'\"]?search_arxiv[`'\"]?", "search_arxiv"),
        (r"I'll use [`'\"]?web_search[`'\"]?", "web_search"),
        (r"I'll use [`'\"]?search_github[`'\"]?", "search_github"),
        (r"I'll use [`'\"]?search_arxiv[`'\"]?", "search_arxiv"),
        (r"use [`'\"]?browse_url[`'\"]?", "browse_url"),
        (r"call [`'\"]?finish[`'\"]?", "finish")
    ]
    
    for pattern, tool_name in thinking_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            # Extract potential query from the thinking section
            query_match = re.search(r'query[:\s]*["\']([^"\']+)["\']', text, re.IGNORECASE)
            if query_match:
                query = query_match.group(1)
                return {"name": tool_name, "arguments": {"query": query}}
            else:
                # Use a generic query based on the context
                return {"name": tool_name, "arguments": {"query": "relevant information"}}
    
    # Strategy 3: Look for any JSON object that resembles a tool call
    # The original patterns had incorrect escaping for raw strings (e.g., \{ instead of \{).
    json_patterns = [
        r'{\s*"name"\s*:\s*"[^"]+",\s*"arguments"\s*:\s*\{.*?\}\s*}',
        r'{\s*"name"\s*:\s*"([^"]+)"\s*,\s*"arguments"\s*:\s*\{[^}]*\}\s*}',
        r'{\s*"name"\s*:\s*"([^"]+)"\s*,\s*"arguments"\s*:\s*\{\s*\}\s*}'
    ]
    
    for pattern in json_patterns:
        # Use re.DOTALL to allow arguments to span multiple lines
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(0))
                if "name" in parsed and "arguments" in parsed:
                    return parsed
            except json.JSONDecodeError:
                continue
    
    # Strategy 4: Default fallback - assume web search with extracted query
    # Look for any quoted strings that might be search queries
    # The original second pattern had a syntax error.
    quote_patterns = [r'"([^"]{10,})"', r"'([^']{10,})'"]
    for pattern in quote_patterns:
        matches = re.findall(pattern, text)
        if matches:
            # Use the longest quoted string as the query
            query = max(matches, key=len)
            return {"name": "web_search", "arguments": {"query": query}}
    
    # If all strategies fail, provide detailed error
    raise ValueError(f"No valid tool call found in response. Content: {text[:300]}...")


def run_web_agent(query: str, max_steps: int = 5) -> dict:
    """
    Runs the web search agent, which uses a ReAct loop to answer a query.
    """
    tools = {
        "web_search": web_search,
        "search_github": search_github,
        "search_arxiv": search_arxiv,
        "browse_url": browse_url,
        "get_github_repo_info": get_github_repo_info,
    }
    
    scratchpad = ""
    sources = []
    final_answer = None

    for i in range(max_steps):
        prompt = WEB_AGENT_PROMPT.format(query=query, scratchpad=scratchpad)
        
        # Get the model's response (thought and action)
        response_text = reasoning_llm.invoke(prompt).content
        
        # Append the thought process to the scratchpad
        scratchpad += f"Step {i+1}: Thought\n{response_text}\n"
        
        try:
            # Extract the action
            action = _extract_tool_code(response_text)
        except ValueError as e:
            # If this is the first step and parsing failed, try a simple retry with explicit format reminder
            if i == 0:
                retry_prompt = f"""IMPORTANT: You MUST respond in the exact format with <tool_code> tags.

{WEB_AGENT_PROMPT.format(query=query, scratchpad="")}

REMINDER: Your response must contain <tool_code>JSON</tool_code> tags."""
                
                retry_response = reasoning_llm.invoke(retry_prompt).content
                scratchpad += f"Step {i+1}: Retry Thought\n{retry_response}\n"
                
                try:
                    action = _extract_tool_code(retry_response)
                except ValueError as retry_e:
                    final_answer = {"summary": f"Agent parsing error after retry: {retry_e}", "sources": list(set(sources))}
                    break
            else:
                final_answer = {"summary": f"Agent parsing error: {e}", "sources": list(set(sources))}
                break
        
        if not action or "name" not in action or "arguments" not in action:
            final_answer = {"summary": "Agent failed to produce a valid action.", "sources": list(set(sources))}
            break

        tool_name = action["name"]
        tool_args = action["arguments"]

        if tool_name == "finish":
            final_answer = {"summary": tool_args.get("answer", "No answer provided."), "sources": list(set(sources))}
            break
            
        if tool_name in tools:
            try:
                # Add URL to sources if browsing
                if tool_name == "browse_url" and "url" in tool_args:
                    sources.append(tool_args["url"])
                elif tool_name == "get_github_repo_info" and "repo_url" in tool_args:
                    sources.append(tool_args["repo_url"])

                observation = tools[tool_name](**tool_args)
                scratchpad += f"Step {i+1}: Observation\n{str(observation)}\n\n"
            except Exception as e:
                observation = f"Error executing tool {tool_name}: {e}"
                scratchpad += f"Step {i+1}: Observation\n{observation}\n\n"
        else:
            observation = f"Unknown tool: {tool_name}"
            scratchpad += f"Step {i+1}: Observation\n{observation}\n\n"
    
    if final_answer is None:
        final_answer = {"summary": "Agent did not finish within the maximum number of steps.", "sources": list(set(sources))}

    return final_answer 