import {test,expect} from "@playwright/test";
test("optimization creates proposal, confirms queued experiment and blocks premature approval",async({page,request})=>{
  await request.post("http://127.0.0.1:28101/control/reset");
  const settings={extraction_model:null,extraction_prompt_version:"55c22bda",cache_enabled:false,retrieval_multiplier:2};
  const state={active_id:null,active:settings,proposals:[] as object[],jobs:[] as object[]};
  await page.route("**/api/backend/ops/optimization**",async route=>{
    if(route.request().method()==="GET")return route.fulfill({json:state});
    if(route.request().url().endsWith("/experiment")){state.jobs=[{id:"job",proposal_id:"proposal",dataset:"cv-extraction-eval",status:"queued",error_code:null}];return route.fulfill({status:202,json:{id:"job"}});}
    state.proposals=[{id:"proposal",settings,status:"proposed",report:null}];return route.fulfill({status:201,json:{id:"proposal"}});
  });
  await page.goto("/login");await page.getByLabel("Tên đăng nhập",{exact:true}).fill("sang");await page.getByLabel("Mật khẩu",{exact:true}).fill("test-password-123");await page.getByRole("button",{name:"Đăng nhập",exact:true}).click();
  await expect(page.getByRole("heading",{name:"Bắt đầu từ một câu hỏi"})).toBeVisible();
  await page.goto("/ops/optimization");
  await page.getByRole("button",{name:"Tạo đề xuất",exact:true}).click();
  await page.getByLabel("Chọn đề xuất",{exact:true}).selectOption("proposal");
  await expect(page.getByRole("button",{name:"Approve",exact:true})).toBeDisabled();
  page.once("dialog",dialog=>dialog.accept());
  await page.getByRole("button",{name:"Chạy experiment",exact:true}).click();
  await expect(page.getByText("cv-extraction-eval · queued",{exact:true})).toBeVisible();
  await expect(page.getByRole("button",{name:"Chạy experiment",exact:true})).toBeDisabled();
});
