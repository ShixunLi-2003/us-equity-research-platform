# 中文使用与求职说明

这个仓库是从美股 500 标的项目提取的可审阅工程版本。代码主线是 Python 研究与 C++ 账户执行，通过 C ABI 连接；示例从合成数据、滚动训练、跨股票排序，到费用后的交易与净值输出完整运行。

按英文 README 的四条命令安装、编译、测试、运行即可。`artifacts/demo` 内包含预测、训练窗口、交易流水和净值。示例收益只用于核对程序行为，不能写成真实投资收益。

面向 Quant Developer，重点讲清楚账户状态、资源释放、订单拒绝、数量取整、费用、公司行动、测试边界，以及为什么把研究和执行分层。不要写“高频撮合”或“生产级低延迟”，项目尚无对应基准和证明。

面向 Quant Research，重点讲清楚信号可用时点、标签何时实现、训练窗口隔离、持仓期对换手的影响，以及多次调参后为何不能继续把已看过区间称为独立测试。真实数据研究仍需要迁移和复核；这个发布版本并未打包所有旧实验。

可据实际贡献改写的英文简历表述：

- Developed a Python/C++ research-to-execution prototype with a C ABI account engine, explicit transaction costs and automated execution tests.
- Implemented a reproducible rolling-window demonstration with label-availability checks, next-session execution and exported prediction/fill/equity artifacts.
- Investigated market-data alignment, corporate-action coverage and Paper order-lifecycle failures in a US-equity research workflow.

只保留你能够解释和现场演示的内容。阅读并理解 AI 辅助生成/修改的代码，按招聘要求如实披露协作方式。不要把未发布的历史模型数量、未经复核的收益或未完成的云端修复写成本仓库已经实现的成果。

当前不含行情、密钥、账户日志、模型权重和第三方因子源码。原始工程继续保留，可在完成数据许可与可复现性审查后分阶段迁入。代码许可需要你确认权利归属后选择。
