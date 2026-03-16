const { web_search } = require('./tools');

async function getDailyBriefing() {
    console.log("=== 早报 - " + new Date().toLocaleString() + " ===\n");
    
    console.log("🌍 国际新闻:\n");
    try {
        const internationalNews = await web_search({ query: "international news", count: 5 });
        if (internationalNews && internationalNews.results) {
            internationalNews.results.forEach((item, index) => {
                console.log(`• ${item.title}`);
            });
        } else {
            console.log("• 获取国际新闻失败");
        }
    } catch (error) {
        console.log("• 获取国际新闻失败");
    }
    
    console.log("\n🤖 AI新闻:\n");
    try {
        const aiNews = await web_search({ query: "artificial intelligence news", count: 5 });
        if (aiNews && aiNews.results) {
            aiNews.results.forEach((item, index) => {
                console.log(`• ${item.title}`);
            });
        } else {
            console.log("• 获取AI新闻失败");
        }
    } catch (error) {
        console.log("• 获取AI新闻失败");
    }
    
    console.log("\n💰 金融知识:\n");
    try {
        const financeNews = await web_search({ query: "financial knowledge education", count: 5 });
        if (financeNews && financeNews.results) {
            financeNews.results.forEach((item, index) => {
                console.log(`• ${item.title}`);
            });
        } else {
            console.log("• 获取金融知识失败");
        }
    } catch (error) {
        console.log("• 获取金融知识失败");
    }
    
    console.log("\n=== 早报结束 ===");
}

getDailyBriefing();