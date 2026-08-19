try {
  rs.status();
  print("MongoDB replica set rs0 already initialized");
} catch (error) {
  if (error.codeName !== "NotYetInitialized" && error.code !== 94) {
    throw error;
  }
  rs.initiate({ _id: "rs0", members: [{ _id: 0, host: "mongodb:27017" }] });
}

for (let attempt = 0; attempt < 60; attempt += 1) {
  if (db.hello().isWritablePrimary) {
    print("MongoDB replica set rs0 is writable");
    break;
  }
  sleep(500);
}

const v2 = db.getSiblingDB("footballpulse_v2");
v2.news_metadata.createIndex({ canonical_url: 1 }, { unique: true });
v2.news_metadata.createIndex({ domain_name: 1, published_time: -1 });
v2.news_metadata.createIndex({ content_hash: 1 });
v2.news_content.createIndex({ cleaned_at: -1 });
v2.news_entities.createIndex({ processed_at: -1 });
v2.news_enrichments.createIndex({ validation_status: 1, processed_at: -1 });
print("MongoDB v2 indexes ensured successfully");
quit(0);
