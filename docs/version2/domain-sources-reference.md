# Domain Sources Reference

Updated: 2026-08-20

Danh sach nay la cac `domain/subpath` uu tien de crawl football news bang tieng Anh. Muc tieu la dung nhu danh sach nguon chuan de tu thiet ke crawler, thay vi phu thuoc truc tiep vao RSS.

## Priority Sources

- `bbc.com/sport/football`
- `theguardian.com/football`
- `nytimes.com/athletic`
- `reuters.com/world/soccer/`
- `espn.com/soccer/`
- `skysports.com/football`
- `cbssports.com/soccer/`
- `goal.com/en`
- `telegraph.co.uk/football`
- `independent.co.uk/sport/football`

## Notes

- Uu tien crawl theo `subpath` de giam nhieu noi dung khong lien quan den football.
- Nhung domain co paywall hoac anti-bot manh nhu `nytimes.com/athletic` va `telegraph.co.uk` can duoc tach rieng trong chinh sach fetch.
- `reuters.com/world/soccer/` phu hop de lay tin tong hop, it giai tri hon so voi cac football portal.
- `goal.com/en`, `espn.com/soccer/`, `skysports.com/football` va `cbssports.com/soccer/` la nhom nguon co mat do bai cao, phu hop de crawl lien tuc.

# Hướng dẫn crawl

## `Hướng dẫn với url:    bbc.com/sport/football`

Đây là danh sách các trang rss.xml cần get link của domain này: 

- “https://feeds.bbci.co.uk/sport/football/league-cup/rss.xml”
- “https://feeds.bbci.co.uk/sport/football/fa-cup/rss.xml”
- “https://feeds.bbci.co.uk/sport/football/europa-league/rss.xml”
- “https://feeds.bbci.co.uk/sport/football/world-cup/rss.xml”
- “https://feeds.bbci.co.uk/sport/football/champions-league/rss.xml”
- “https://feeds.bbci.co.uk/sport/football/rss.xml”
- “https://feeds.bbci.co.uk/sport/football/european/rss.xml”
- “https://feeds.bbci.co.uk/sport/football/premier-league/rss.xml”

Đây là một ví dụ về dữ liệu trong rss.xml:

```
<rss xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:media="http://search.yahoo.com/mrss/" version="2.0">
<channel>
<title>
<![CDATA[ BBC Sport ]]>
</title>
<description>
<![CDATA[ BBC Sport - Premier League ]]>
</description>
<link>https://www.bbc.co.uk/sport/football/premier-league</link>
<image>
<url>http://news.bbc.co.uk/sol/shared/img/sport_120x60.gif</url>
<title>BBC Sport</title>
<link>https://www.bbc.co.uk/sport/football/premier-league</link>
</image>
<generator>RSS for Node</generator>
<lastBuildDate>Thu, 20 Aug 2026 08:11:10 GMT</lastBuildDate>
<atom:link href="https://feeds.bbci.co.uk/sport/football/premier-league/rss.xml" rel="self" type="application/rss+xml"/>
<copyright>
<![CDATA[ Copyright: (C) British Broadcasting Corporation, see https://www.bbc.co.uk/usingthebbc/terms-of-use/#15metadataandrssfeeds for terms and conditions of reuse. ]]>
</copyright>
<language>
<![CDATA[ en-gb ]]>
</language>
<ttl>15</ttl>
<item>
<title>
<![CDATA[ Premier League predictions 2026-27: BBC Sport pundits pick their top four ]]>
</title>
<description>
<![CDATA[ We ask 26 BBC Sport football pundits to predict who will win the 2026-27 Premier League title, and which clubs will finish in the top four. ]]>
</description>
<link>https://www.bbc.co.uk/sport/football/articles/cp8edryd7plo?at_medium=RSS&at_campaign=rss</link>
<guid isPermaLink="false">https://www.bbc.co.uk/sport/football/articles/cp8edryd7plo#0</guid>
<pubDate>Thu, 20 Aug 2026 05:24:16 GMT</pubDate>
<media:thumbnail width="240" height="134" url="https://ichef.bbci.co.uk/ace/standard/240/cpsprodpb/86f1/live/4444d1b0-9bb6-11f1-b109-879e35c24276.jpg"/>
</item>
<item>
<title>
<![CDATA[ Minority investment or takeover - what does Bezos' Liverpool deal mean? ]]>
</title>
<description>
<![CDATA[ What does Liverpool’s future hold following the sale of stakes to 1892 Holdings, and how involved will Amazon founder Jeff Bezos be? ]]>
</description>
<link>https://www.bbc.co.uk/sport/football/articles/c4g31egre74o?at_medium=RSS&at_campaign=rss</link>
<guid isPermaLink="false">https://www.bbc.co.uk/sport/football/articles/c4g31egre74o#0</guid>
<pubDate>Thu, 20 Aug 2026 07:03:28 GMT</pubDate>
<media:thumbnail width="240" height="135" url="https://ichef.bbci.co.uk/ace/standard/240/cpsprodpb/ba77/live/a282ad60-9bf2-11f1-8470-d18257d2d589.jpg"/>
</item>
<item>
<title>
<![CDATA[ Arsenal agree £50m-plus deal to sign Villa's Konsa ]]>
</title>
<description>
<![CDATA[ Arsenal agree a deal worth more than £50m to sign Aston Villa and England defender Ezri Konsa. ]]>
</description>
<link>https://www.bbc.co.uk/sport/football/articles/c98vz9jvg0vo?at_medium=RSS&at_campaign=rss</link>
<guid isPermaLink="false">https://www.bbc.co.uk/sport/football/articles/c98vz9jvg0vo#0</guid>
<pubDate>Wed, 19 Aug 2026 13:55:18 GMT</pubDate>
<media:thumbnail width="240" height="135" url="https://ichef.bbci.co.uk/ace/standard/240/cpsprodpb/ae9d/live/ad505a30-9bbb-11f1-ae8a-8d57110c5ba6.jpg"/>
</item>
<item>
<title>
<![CDATA[ Inter agree £30m deal for Liverpool's Jones ]]>
</title>
<description>
<![CDATA[ Curtis Jones is set to join Inter Milan after the Italian side agreed a deal worth 35m euros (£30m) with Liverpool. ]]>
</description>
<link>https://www.bbc.co.uk/sport/football/articles/clye43vge5jo?at_medium=RSS&at_campaign=rss</link>
<guid isPermaLink="false">https://www.bbc.co.uk/sport/football/articles/clye43vge5jo#0</guid>
<pubDate>Thu, 20 Aug 2026 07:57:12 GMT</pubDate>
<media:thumbnail width="240" height="134" url="https://ichef.bbci.co.uk/ace/standard/240/cpsprodpb/3d51/live/eeaadb30-9bd5-11f1-bd98-ed4222d45acc.jpg"/>
</item>
<item>
```

Tôi cần bạn lấy ra các url mà nằm trong 30 ngày gần nhất.  nhớ là các url phải có chứa từ “articles” nhé.

## trang : `theguardian.com/football`

Đây  là trang rss : “https://www.theguardian.com/football/rss”

đây là dữ liệu ví dụ trong trang kia

```
<rss xmlns:media="http://search.yahoo.com/mrss/" xmlns:dc="http://purl.org/dc/elements/1.1/" version="2.0">
<channel>
<title>Football | The Guardian</title>
<link>https://www.theguardian.com/football</link>
<description>Latest Football news, comment and analysis from the Guardian, the world's leading liberal voice</description>
<language>en-gb</language>
<copyright>Guardian News and Media Limited or its affiliated companies. All rights reserved. 2026</copyright>
<pubDate>Thu, 20 Aug 2026 08:11:36 GMT</pubDate>
<dc:date>2026-08-20T08:11:36Z</dc:date>
<dc:language>en-gb</dc:language>
<dc:rights>Guardian News and Media Limited or its affiliated companies. All rights reserved. 2026</dc:rights>
<image>
<title>The Guardian</title>
<url>https://assets.guim.co.uk/images/guardian-logo-rss.c45beb1bafa34b347ac333af2e6fe23f.png</url>
<link>https://www.theguardian.com</link>
</image>
<item>
<title>Fifth Fifa vice-president turns against Infantino, saying he has ‘lost confidence’ in him</title>
<link>https://www.theguardian.com/football/2026/aug/19/fifth-fifa-vice-president-turns-against-infantino-saying-he-has-lost-confidence-in-him</link>
<description><ul><li><p>Hungary’s Sandor Csanyi highly critical of Fifa president</p></li><li><p>He cites dismissal of COO Kevin Lamour as ‘final straw’</p></li></ul><p>Gianni Infantino has lost the support of another one of Fifa’s vice-presidents, with the Hungarian football federation chief, Sandor Csanyi, criticising the president’s “professional judgment, ethical standards and leadership”.</p><p>In an explosive letter sent to Infantino on Tuesday, which was first obtained by the news agency Agence France-Presse, Csanyi states that he has “lost the confidence I previously placed in you” and describes the “unexpected dismissal” of Fifa’s chief operating officer, Kevin Lamour, as the “final straw”.</p> <a href="https://www.theguardian.com/football/2026/aug/19/fifth-fifa-vice-president-turns-against-infantino-saying-he-has-lost-confidence-in-him">Continue reading...</a></description>
<category domain="https://www.theguardian.com/football/gianni-infantino">Gianni Infantino</category>
<category domain="https://www.theguardian.com/football/fifa">Fifa</category>
<category domain="https://www.theguardian.com/football/football">Football</category>
<category domain="https://www.theguardian.com/football/footballpolitics">Football politics</category>
<category domain="https://www.theguardian.com/sport/sport">Sport</category>
<pubDate>Wed, 19 Aug 2026 19:04:48 GMT</pubDate>
<guid>https://www.theguardian.com/football/2026/aug/19/fifth-fifa-vice-president-turns-against-infantino-saying-he-has-lost-confidence-in-him</guid>
<media:content width="140" url="https://i.guim.co.uk/img/media/96f0cd8b5d7de094404335c8e5cfd3353bb95f98/1222_2_2430_1944/master/2430.jpg?width=140&quality=85&auto=format&fit=max&s=c64b1dc0243e851093fb3281554f8d9a">
<media:credit scheme="urn:ebu">Photograph: Christopher Neundorf/EPA</media:credit>
</media:content>
<media:content width="460" url="https://i.guim.co.uk/img/media/96f0cd8b5d7de094404335c8e5cfd3353bb95f98/1222_2_2430_1944/master/2430.jpg?width=460&quality=85&auto=format&fit=max&s=e9b549c9f7575058d390c6d73352ceab">
<media:credit scheme="urn:ebu">Photograph: Christopher Neundorf/EPA</media:credit>
</media:content>
<media:content width="700" url="https://i.guim.co.uk/img/media/96f0cd8b5d7de094404335c8e5cfd3353bb95f98/1222_2_2430_1944/master/2430.jpg?width=700&quality=85&auto=format&fit=max&s=99014d8eb96fcbf258f66aaeb1946ccf">
<media:credit scheme="urn:ebu">Photograph: Christopher Neundorf/EPA</media:credit>
</media:content>
<dc:creator>Matt Hughes</dc:creator>
<dc:date>2026-08-19T19:04:48Z</dc:date>
</item>
<item>
<title>Frugal or foolish? Manchester United may regret not backing Carrick</title>
<link>https://www.theguardian.com/football/2026/aug/20/manchester-united-may-regret-not-backing-michael-carrick</link>
<description><p>Another left-back has been a priority all summer, but there seems to be no sign of one coming to Old Trafford</p><p>After <a href="https://www.theguardian.com/football/2019/jun/29/manchester-united-complete-45m-signing-of-aaron-wan-bissaka">signing Aaron Wan-Bissaka</a> in 2019, Manchester United’s PR machine boasted they had scouted 804 right-backs before landing on the Crystal Palace player. At the time it felt like an&nbsp;unnecessary brag, designed to&nbsp;convince fans and journalists the&nbsp;club were doing their due diligence when it came to scouting and data.</p><p>Now, as the search for a left-back to challenge Luke Shaw drags on with less than two weeks of the summer transfer window remaining, there seems to be a lack of credible targets.</p> <a href="https://www.theguardian.com/football/2026/aug/20/manchester-united-may-regret-not-backing-michael-carrick">Continue reading...</a></description>
<category domain="https://www.theguardian.com/football/manchester-united">Manchester United</category>
<category domain="https://www.theguardian.com/football/transfer-window">Transfer window</category>
<category domain="https://www.theguardian.com/football/football">Football</category>
<category domain="https://www.theguardian.com/sport/sport">Sport</category>
<category domain="https://www.theguardian.com/football/michael-carrick">Michael Carrick</category>
<pubDate>Thu, 20 Aug 2026 07:00:46 GMT</pubDate>
<guid>https://www.theguardian.com/football/2026/aug/20/manchester-united-may-regret-not-backing-michael-carrick</guid>
<media:content width="140" url="https://i.guim.co.uk/img/media/6a542e4126ae6a36e0e92f8262dfdc68bf9629ea/0_0_5200_4160/master/5200.jpg?width=140&quality=85&auto=format&fit=max&s=f44682f04f06d8f801a124a865ec8538">
<media:credit scheme="urn:ebu">Photograph: Grzegorz Wajda/SOPA Images/Shutterstock</media:credit>
</media:content>
<media:content width="460" url="https://i.guim.co.uk/img/media/6a542e4126ae6a36e0e92f8262dfdc68bf9629ea/0_0_5200_4160/master/5200.jpg?width=460&quality=85&auto=format&fit=max&s=598beb7c525f55711f875ad4e8600808">
<media:credit scheme="urn:ebu">Photograph: Grzegorz Wajda/SOPA Images/Shutterstock</media:credit>
</media:content>
<media:content width="700" url="https://i.guim.co.uk/img/media/6a542e4126ae6a36e0e92f8262dfdc68bf9629ea/0_0_5200_4160/master/5200.jpg?width=700&quality=85&auto=format&fit=max&s=3f3b87a5478f23fa6ed0a672c365a505">
<media:credit scheme="urn:ebu">Photograph: Grzegorz Wajda/SOPA Images/Shutterstock</media:credit>
</media:content>
<dc:creator>Dominic Booth</dc:creator>
<dc:date>2026-08-20T07:00:46Z</dc:date>
</item>
```

Tôi cần bạn lấy ra các url mà nằm trong 30 ngày gần nhất. 

## Trang : `nytimes.com/athletic`

đây là trang rss: “https://www.nytimes.com/athletic/rss/football/”

đây là dữ liệu trong đó:

```
<rss xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:media="http://search.yahoo.com/mrss/" version="2.0">
<channel>
<title>
<![CDATA[ Soccer - The Athletic ]]>
</title>
<description>
<![CDATA[ Soccer - The Athletic ]]>
</description>
<link>https://www.nytimes.com/athletic/football/soccer/</link>
<image>
<url>https://www.nytimes.com/athletic/static/img/transparent-background-dark-favicon-144x144.png</url>
<title>Soccer - The Athletic</title>
<link>https://www.nytimes.com/athletic/football/soccer/</link>
</image>
<generator>The Athletic Media Company</generator>
<lastBuildDate>Thu, 20 Aug 2026 08:28:32 GMT</lastBuildDate>
<atom:link href="https://www.nytimes.com/athletic/rss/football/" rel="self" type="application/rss+xml"/>
<pubDate>Thu, 20 Aug 2026 04:16:55 GMT</pubDate>
<copyright>
<![CDATA[ 2026 The Athletic Media Company, A New York Times Company ]]>
</copyright>
<language>
<![CDATA[ en ]]>
</language>
<item>
<title>
<![CDATA[ Trent Alexander-Arnold, Jose Mourinho and a crucial second season at Real Madrid ]]>
</title>
<description>
<![CDATA[ Alexander-Arnold experienced a mixed first campaign at the Bernabeu but is set to play a key role in Mourinho's rebuild ]]>
</description>
<link>https://www.nytimes.com/athletic/7524209/2026/08/20/trent-alexander-arnold-jose-mourinho-real-madrid-analysis/</link>
<guid isPermaLink="true">https://www.nytimes.com/athletic/7524209/2026/08/20/trent-alexander-arnold-jose-mourinho-real-madrid-analysis/</guid>
<pubDate>Thu, 20 Aug 2026 04:16:55 GMT</pubDate>
<media:content url="https://static01.nyt.com/athletic/uploads/wp/2026/08/19121601/GettyImages-2290319884-scaled.jpg"/>
<media:description type="html">Trent Alexander-Arnold had a mixed first campaign at the Bernabeu</media:description>
</item>
<item>
<title>
<![CDATA[ Premier League predictions are back, join us: Arsenal vs Coventry and the rest of GW1 ]]>
</title>
<description>
<![CDATA[ Our weekly predictions are back with new experts. Join us to see their views on the first 10 games of the season ]]>
</description>
<link>https://www.nytimes.com/athletic/7523396/2026/08/20/premier-league-predictions-gameweek-1/</link>
<guid isPermaLink="true">https://www.nytimes.com/athletic/7523396/2026/08/20/premier-league-predictions-gameweek-1/</guid>
<pubDate>Thu, 20 Aug 2026 04:14:57 GMT</pubDate>
<media:content url="https://static01.nyt.com/athletic/uploads/wp/2026/08/19154926/0820_PL_Predictions_Wk1-1.png"/>
<media:description type="html"/>
</item>
<item>
<title>
<![CDATA[ The extraordinary fall and rise of Coventry City ]]>
</title>
<description>
<![CDATA[ The club survived exile from its own stadium, going into administration and relegation to the fourth tier before its recent renaissance ]]>
</description>
<link>https://www.nytimes.com/athletic/7518787/2026/08/20/coventry-city-premier-league-extraordinary-fall-and-rise/</link>
<guid isPermaLink="true">https://www.nytimes.com/athletic/7518787/2026/08/20/coventry-city-premier-league-extraordinary-fall-and-rise/</guid>
<pubDate>Thu, 20 Aug 2026 04:13:47 GMT</pubDate>
<media:content url="https://static01.nyt.com/athletic/uploads/wp/2026/08/19102927/0820_Cov-scaled.jpg"/>
<media:description type="html"/>
</item>
<item>
<title>
<![CDATA[ Manchester United's Andrey Santos is an 'exemplary player'. Can he be a Premier League star? ]]>
</title>
<description>
<![CDATA[ The Athletic spoke two people who have coached Santos. Their message is clear: trust him ]]>
</description>
<link>https://www.nytimes.com/athletic/7521853/2026/08/20/andrey-santos-manchester-united-profile/</link>
<guid isPermaLink="true">https://www.nytimes.com/athletic/7521853/2026/08/20/andrey-santos-manchester-united-profile/</guid>
<pubDate>Thu, 20 Aug 2026 04:12:40 GMT</pubDate>
<media:content url="https://static01.nyt.com/athletic/uploads/wp/2026/08/19094812/GettyImages-2289722207-1-scaled-e1787147335142.jpg"/>
<media:description type="html">Andrey Santos of Manchester United after the pre-season friendly match between Manchester United and Leeds United at Croke Park in Dublin. (Photo By David Fitzgerald/Sportsfile via Getty Images)</media:description>
</item>
```

Lấy ra danh sách url của các bài báo có pubDate trong vòng 30 ngày gần nhất

## Trang: `reuters.com/world/soccer/`

ko tìm được rss hoặc sitemap

## TRang: “`espn.com/soccer/"`

ko tìm được rss hoặc sitemap

## trang: “`skysports.com/football"`

ko tìm được.

## trang: `cbssports.com/soccer/`

ko tìm thấy.

## trang “`goal.com/en"`

ko thấy

## trang: “`telegraph.co.uk/football"`

đây là 2 trang rss :

- “https://feeds.bbci.co.uk/sport/football/rss.xml”
- “https://www.telegraph.co.uk/football/sitemap-0.xml”

nhớ là lấy ra danh sách các url của 30 ngày gần nhất

## trang “`independent.co.uk/sport/football`

link rss: “https://www.independent.co.uk/sport/football/rss”

nhớ là lấy ra danh sách các url của 30 ngày gần nhất