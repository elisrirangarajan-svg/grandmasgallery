const FOLDER_ID = "1Bqmt9lUV_gCC0tNsXPGPkE9HgyGFF5y2";

function doGet() {
  try {
    const folder = DriveApp.getFolderById(FOLDER_ID);
    const files = folder.getFiles();
    const memories = [];
    while (files.hasNext()) {
      const file = files.next();
      const mimeType = file.getMimeType();
      if (!mimeType || !mimeType.startsWith("image/")) continue;
      const id = file.getId();
      memories.push({id:id,name:file.getName(),url:"https://drive.google.com/thumbnail?id=" + encodeURIComponent(id) + "&sz=w1600"});
    }
    memories.sort(function(a,b){return a.name.localeCompare(b.name);});
    return ContentService.createTextOutput(JSON.stringify({ok:true,count:memories.length,memories:memories})).setMimeType(ContentService.MimeType.JSON);
  } catch (error) {
    return ContentService.createTextOutput(JSON.stringify({ok:false,error:String(error)})).setMimeType(ContentService.MimeType.JSON);
  }
}
