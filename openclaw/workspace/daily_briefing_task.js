// Daily Briefing Task
// This script fetches and sends daily briefing at 9 AM

async function runDailyBriefing() {
  // Check current hour
  const currentHour = new Date().getHours();
  
  // Only run at 9 AM
  if (currentHour !== 9) {
    console.log("Not 9 AM yet, skipping daily briefing");
    return;
  }
  
  // Check if we already sent today's briefing
  const today = new Date().toISOString().split('T')[0];
  const fs = require('fs');
  
  const flagFile = `/tmp/daily_briefing_sent_${today}`;
  if (fs.existsSync(flagFile)) {
    console.log("Daily briefing already sent today");
    return;
  }
  
  try {
    console.log("=== 早报 - " + new Date().toLocaleString('zh-CN') + " ===\n");
    
    console.log("🌍 国际新闻:\n");
    const internationalNews = await web_search({ query: "international news", count: 5 });
    if (internationalNews && internationalNews.results) {
      internationalNews.results.forEach((item, index) => {
        console.log(`${index + 1}. ${item.title}`);
        console.log(`   来源: ${item.url}\n`);
      });
    } else {
      console.log("• 获取国际新闻失败\n");
    }
    
    console.log("🤖 AI新闻:\n");
    const aiNews = await web_search({ query: "artificial intelligence news latest", count: 5 });
    if (aiNews && aiNews.results) {
      aiNews.results.forEach((item, index) => {
        console.log(`${index + 1}. ${item.title}`);
        console.log(`   来源: ${item.url}\n`);
      });
    } else {
      console.log("• 获取AI新闻失败\n");
    }
    
    console.log("💰 金融知识:\n");
    const financeKnowledge = await web_search({ query: "financial knowledge education basics", count: 5 });
    if (financeKnowledge && financeKnowledge.results) {
      financeKnowledge.results.forEach((item, index) => {
        console.log(`${index + 1}. ${item.title}`);
        console.log(`   来源: ${item.url}\n`);
      });
    } else {
      console.log("• 获取金融知识失败\n");
    }
    
    console.log("=== 早报结束 ===");
    
    // Create flag file to indicate we sent today's briefing
    fs.writeFileSync(flagFile, "sent");
    console.log("Daily briefing sent and flag file created.");
    
  } catch (error) {
    console.error("Error sending daily briefing:", error);
  }
}

// Execute the function
runDailyBriefing();