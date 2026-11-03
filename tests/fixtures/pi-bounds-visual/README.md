# π几何夹逼测试输入

`plan.json` 与 `narration-draft-v001.json` 是独立可提交的便携输入；不读取被忽略的 runtime 或 outputs。项目当前计划由主控后续管理，fixture 仅保护这次作者冻结的内容合同。

`native-clock.json` 记录共用 `lesson_native_harness` 执行真实 ManimGL 动画 begin/interpolate/finish 与 update_mobjects 后的 30fps 时钟。中文、TeX、数字用矢量占位；不建 GL 相机、不渲染、不编译 TeX、不生成声音。它不是像素、版式或独立质量批准。

纯数学测试使用有理区间重算种子、勾股半角递推、定向舍入、单调性、五位舍入单元；测试可用 π 与三角函数作 oracle，数值界生产函数不能使用它们。局部三角不等式和实际 n 条轮廓也分别验证。

写入者：本题数学作者；消费者：pytest 与主控；生命周期：此源码/计划/native API 组合；任一输入变化即需重跑并版本化，真实像素始终另审。
