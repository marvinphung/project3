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
    quit(0);
  }
  sleep(500);
}

throw new Error("MongoDB replica set rs0 did not elect a primary");
